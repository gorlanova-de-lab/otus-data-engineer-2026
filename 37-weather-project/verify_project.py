"""Read-only verification of the weather warehouse; outputs no credentials."""
import json
import psycopg2
with psycopg2.connect("") as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*),count(DISTINCT(city,observed_date)),min(observed_date),max(observed_date) FROM stg.weather_daily")
        staging=cur.fetchone()
        cur.execute("SELECT city,count(*),min(observed_date),max(observed_date),sum(precipitation) FROM mart.weather_daily GROUP BY city ORDER BY city")
        cities=cur.fetchall()
        cur.execute("SELECT count(*),sum(observed_days),sum(precipitation_total) FROM mart.weather_monthly")
        monthly,monthly_days,monthly_rain=cur.fetchone()
        cur.execute("SELECT run_id,status,rows_loaded FROM audit.runs WHERE status='success' ORDER BY started_at DESC LIMIT 2")
        runs=cur.fetchall()
        cur.execute("SELECT count(*) FROM raw.weather_responses")
        raw_count=cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM audit.runs WHERE status='failed' AND error LIKE '%2000-01-01%'")
        rollback_tests=cur.fetchone()[0]
assert staging[0]==staging[1]
assert len(cities)==2 and all(c[1]==90 for c in cities)
assert monthly_days==180
assert monthly_rain==sum(c[4] for c in cities)
assert len(runs)==2 and all(r[1]=='success' and r[2]==180 for r in runs)

print(json.dumps({'checks':'PASS','staging_rows':staging[0],'staging_unique_city_days':staging[1],
 'history_start':staging[2],'history_end':staging[3],'mart_city_rows':cities,'monthly_rows':monthly,
 'last_two_successful_runs':runs,'raw_response_count':raw_count,'expected_rollback_test_audits':rollback_tests},default=str,ensure_ascii=False,indent=2))
