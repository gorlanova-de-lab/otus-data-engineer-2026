"""Daily, idempotent API -> raw -> staging -> mart workflow with audit."""
import argparse
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import time
import uuid
from datetime import date, timedelta
import psycopg2
from psycopg2.extras import Json, execute_values
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LOG = logging.getLogger("weather")
CITIES = {"Berlin": (52.52, 13.405), "Madrid": (40.4168, -3.7038)}


def validate_daily(daily):
    fields = ("time", "temperature_2m_max", "temperature_2m_min", "precipitation_sum")
    lengths = {len(daily[key]) for key in fields}
    if len(lengths) != 1 or not daily["time"]:
        raise ValueError("Missing or unequal-length daily arrays")
    result = []
    for day, high, low, rain in zip(*(daily[key] for key in fields)):
        parsed_day = date.fromisoformat(day)
        if any(v is None or not math.isfinite(float(v)) for v in (high, low, rain)):
            raise ValueError(f"Missing/nonfinite observations for {day}")
        if low > high or rain < 0 or not (-100 <= low <= high <= 70):
            raise ValueError(f"Invalid observations for {day}")
        result.append((parsed_day, high, low, rain))
    if len({row[0] for row in result}) != len(result):
        raise ValueError("Duplicate observation dates")
    return result


def run_once(start=None, end=None):
    end = end or date.today()-timedelta(days=7)
    start = start or end-timedelta(days=89)
    run_id = str(uuid.uuid4())
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=Retry(
        total=3, backoff_factor=1, status_forcelist=[429,500,502,503,504], allowed_methods=["GET"])))
    with psycopg2.connect("") as conn:
        with conn.cursor() as cur:
            cur.execute(Path(__file__).with_name("schema.sql").read_text())
            cur.execute("INSERT INTO audit.runs(run_id,status) VALUES(%s,'running')",(run_id,))
        conn.commit()
        try:
            loaded = 0
            for city,(lat,lng) in CITIES.items():
                response = session.get("https://archive-api.open-meteo.com/v1/archive",params={
                    "latitude":lat,"longitude":lng,"start_date":start.isoformat(),"end_date":end.isoformat(),
                    "daily":"temperature_2m_max,temperature_2m_min,precipitation_sum",
                    "timezone":"UTC","models":"era5"},timeout=(10,60))
                response.raise_for_status()
                payload = response.json()
                daily = payload["daily"]
                rows = validate_daily(daily)
                expected = (end-start).days+1
                if len(rows) != expected or min(r[0] for r in rows) != start or max(r[0] for r in rows) != end:
                    raise ValueError(f"Incomplete API period for {city}")
                digest = hashlib.sha256(json.dumps(daily,sort_keys=True,separators=(",",":")).encode()).hexdigest()
                with conn.cursor() as cur:
                    cur.execute("""INSERT INTO raw.weather_responses(city,payload_hash,payload,run_id)
                        VALUES(%s,%s,%s,%s) ON CONFLICT(city,payload_hash)
                        DO UPDATE SET payload_hash=excluded.payload_hash RETURNING response_id""",
                        (city,digest,Json(payload),run_id))
                    response_id = cur.fetchone()[0]
                    execute_values(cur,"""INSERT INTO stg.weather_daily
                        (city,observed_date,temp_max,temp_min,precipitation,response_id) VALUES %s
                        ON CONFLICT(city,observed_date) DO UPDATE SET temp_max=excluded.temp_max,
                        temp_min=excluded.temp_min,precipitation=excluded.precipitation,
                        response_id=excluded.response_id,updated_at=now()""",
                        [(city,*row,response_id) for row in rows])
                loaded += len(rows)
                LOG.info("validated city=%s rows=%s",city,len(rows))
            with conn.cursor() as cur:
                cur.execute("UPDATE audit.runs SET status='success',finished_at=now(),rows_loaded=%s WHERE run_id=%s",(loaded,run_id))
            conn.commit()
            LOG.info("SUCCESS run=%s rows=%s",run_id,loaded)
            return loaded
        except Exception as exc:
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute("UPDATE audit.runs SET status='failed',finished_at=now(),error=%s WHERE run_id=%s",(str(exc)[:2000],run_id))
            conn.commit()
            raise
        finally:
            session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    parser=argparse.ArgumentParser()
    parser.add_argument("--once",action="store_true")
    parser.add_argument("--start",type=date.fromisoformat)
    parser.add_argument("--end",type=date.fromisoformat)
    args=parser.parse_args()
    if args.once:
        run_once(args.start,args.end)
    else:
        while True:
            try:
                run_once(args.start,args.end)
            except Exception:
                LOG.exception("Workflow failed; audit recorded; will retry at next interval")
            time.sleep(int(os.getenv("INTERVAL_SECONDS","86400")))
