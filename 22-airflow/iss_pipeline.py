"""Observe the ISS every 30 minutes and store validated observations."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
import requests
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook


@dag(dag_id="iss_position_to_postgres", schedule="*/30 * * * *",
     start_date=datetime(2026, 10, 1, tzinfo=timezone.utc), catchup=False,
     max_active_runs=1, default_args={"retries": 2, "retry_delay": timedelta(minutes=2)},
     tags=["otus", "api", "postgres"])
def iss_pipeline():
    @task
    def fetch():
        response = requests.get(os.getenv("ISS_API_URL", "http://api.open-notify.org/iss-now.json"), timeout=(10, 30))
        response.raise_for_status()
        return response.json()

    @task
    def parse(payload):
        if payload.get("message") != "success":
            raise ValueError("ISS API did not report success")
        observed_at = datetime.fromtimestamp(int(payload["timestamp"]), tz=timezone.utc)
        lat = Decimal(payload["iss_position"]["latitude"])
        lng = Decimal(payload["iss_position"]["longitude"])
        if not lat.is_finite() or not lng.is_finite() or not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValueError("Invalid coordinates")
        if abs((datetime.now(timezone.utc) - observed_at).total_seconds()) > 600:
            raise ValueError("ISS response is stale or from the future")
        return {"observed_at": observed_at.isoformat(), "latitude":str(lat), "longitude":str(lng)}

    @task
    def load(record, **context):
        hook = PostgresHook(postgres_conn_id="analytics_pg")
        with hook.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS iss_observations (
                        observed_at TIMESTAMPTZ PRIMARY KEY,
                        latitude NUMERIC(9,6) NOT NULL CHECK(latitude BETWEEN -90 AND 90),
                        longitude NUMERIC(9,6) NOT NULL CHECK(longitude BETWEEN -180 AND 180),
                        collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        dag_run_id TEXT NOT NULL,
                        data_interval_start TIMESTAMPTZ NOT NULL,
                        data_interval_end TIMESTAMPTZ NOT NULL
                    )""")
                cur.execute("""
                    INSERT INTO iss_observations
                      (observed_at,latitude,longitude,dag_run_id,data_interval_start,data_interval_end)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(observed_at) DO NOTHING
                    """, (record["observed_at"],record["latitude"],record["longitude"],
                          context["run_id"],context["data_interval_start"],context["data_interval_end"]))
        return record

    load(parse(fetch()))


iss_pipeline()
