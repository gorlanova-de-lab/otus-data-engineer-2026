CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS mart;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE TABLE IF NOT EXISTS audit.runs (
 run_id UUID PRIMARY KEY, started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 finished_at TIMESTAMPTZ, status TEXT NOT NULL, rows_loaded INT, error TEXT
);
CREATE TABLE IF NOT EXISTS raw.weather_responses (
 response_id BIGSERIAL PRIMARY KEY, city TEXT NOT NULL,
 payload_hash TEXT NOT NULL, payload JSONB NOT NULL,
 loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 run_id UUID NOT NULL REFERENCES audit.runs,
 UNIQUE(city,payload_hash)
);
CREATE TABLE IF NOT EXISTS stg.weather_daily (
 city TEXT NOT NULL, observed_date DATE NOT NULL,
 temp_max NUMERIC(6,2) NOT NULL, temp_min NUMERIC(6,2) NOT NULL,
 precipitation NUMERIC(8,2) NOT NULL CHECK(precipitation >= 0),
 response_id BIGINT NOT NULL REFERENCES raw.weather_responses,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY(city,observed_date), CHECK(temp_min <= temp_max)
);
CREATE OR REPLACE VIEW mart.weather_daily AS
 SELECT city,observed_date,temp_max,temp_min,precipitation,
        round((temp_max+temp_min)/2,2) AS temp_midpoint,
        temp_max-temp_min AS daily_range,
        CASE WHEN precipitation >= 10 THEN 'heavy rain'
             WHEN precipitation > 0 THEN 'rain' ELSE 'dry' END AS rain_category
 FROM stg.weather_daily;
CREATE OR REPLACE VIEW mart.weather_monthly AS
 SELECT city,date_trunc('month',observed_date)::date AS month,
        count(*) AS observed_days,round(avg(temp_midpoint),2) AS avg_temp_midpoint,
        sum(precipitation) AS precipitation_total,
        count(*) FILTER(WHERE precipitation > 0) AS rainy_days
 FROM mart.weather_daily GROUP BY city,date_trunc('month',observed_date);
