"""Database integration test; mocked API is used only to force a rollback."""
from datetime import date
from unittest.mock import patch
import psycopg2
import pipeline

class Response:
    def __init__(self, broken): self.broken=broken
    def raise_for_status(self): pass
    def json(self):
        return {"daily_units":{"temperature_2m_max":"°C","temperature_2m_min":"°C","precipitation_sum":"mm"},
                "daily":{"time":["2000-01-01"],"temperature_2m_max":[5 if self.broken else 20],
                         "temperature_2m_min":[10],"precipitation_sum":[0]}}
class Session:
    def __init__(self): self.calls=0
    def mount(self,*args): pass
    def get(self,*args,**kwargs):
        self.calls+=1
        return Response(self.calls==2)
    def close(self): pass

def counts():
    with psycopg2.connect("") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT (SELECT count(*) FROM raw.weather_responses), (SELECT count(*) FROM stg.weather_daily), (SELECT count(*) FROM audit.runs)")
            return cur.fetchone()
before=counts()
with patch.object(pipeline.requests,"Session",Session):
    try:
        pipeline.run_once(date(2000,1,1),date(2000,1,1))
    except ValueError as error:
        assert "Invalid observations" in str(error)
    else:
        raise AssertionError("Invalid second-city response was not rejected")
after=counts()
assert after[:2]==before[:2], (before,after)
assert after[2]==before[2]+1
with psycopg2.connect("") as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT status,error FROM audit.runs ORDER BY started_at DESC LIMIT 1")
        status,error=cur.fetchone()
        assert status=="failed" and "2000-01-01" in error
print("PASS: invalid second-city response rolled back both raw and staging; failed audit retained. This is a test fixture, not real weather data.")
