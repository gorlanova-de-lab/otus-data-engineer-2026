-- Run against the managed PostgreSQL database analytics.
SELECT current_database(), version();
SELECT count(*) AS observations,
       count(DISTINCT data_interval_start) AS periods,
       min(observed_at) AS first_observation,
       max(observed_at) AS last_observation
FROM iss_observations;
SELECT observed_at, latitude, longitude, dag_run_id,
       data_interval_start, data_interval_end
FROM iss_observations
ORDER BY observed_at;
