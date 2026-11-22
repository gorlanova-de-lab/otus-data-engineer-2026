"""Reproduce a local Metabase dashboard; secrets are read from .env, never exported."""
import json
import os
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parent
for line in (ROOT/".env").read_text().splitlines():
    if line and not line.startswith("#") and "=" in line:
        key,value=line.split("=",1)
        os.environ.setdefault(key,value)
URL=os.getenv("METABASE_URL","http://localhost:3000")
session=requests.Session()

def call(method,path,body=None):
    response=session.request(method,URL+"/api/"+path,json=body,timeout=90)
    if not response.ok:
        raise RuntimeError(f"Metabase {method} {path}: HTTP {response.status_code} {response.text[:600]}")
    return response.json() if response.content else None

props=call("GET","session/properties")
if props.get("setup-token") and not props.get("has-user-setup", False):
    login=call("POST","setup",{"token":props["setup-token"],
        "user":{"email":"otus@example.com","first_name":"OTUS","last_name":"Learner",
                "password":os.environ["METABASE_PASSWORD"]},
        "prefs":{"site_name":"OTUS Weather Analytics","site_locale":"en"}})
else:
    login=call("POST","session",{"username":"otus@example.com","password":os.environ["METABASE_PASSWORD"]})
session.headers["X-Metabase-Session"]=login["id"]
databases=call("GET","database")
databases=databases.get("data",databases) if isinstance(databases,dict) else databases
db=next((item for item in databases if item["name"]=="Weather warehouse"),None)
if db is None:
    db=call("POST","database",{"name":"Weather warehouse","engine":"postgres",
        "details":{"host":"postgres","port":5432,"dbname":"weather","user":"weather",
                   "password":os.environ["POSTGRES_PASSWORD"],"ssl":False},"is_full_sync":True})
dashboards=call("GET","dashboard")
dashboards=dashboards.get("data",dashboards) if isinstance(dashboards,dict) else dashboards
dash=next((item for item in dashboards if item["name"]=="Weather: Berlin and Madrid"),None)
if dash is None:
    dash=call("POST","dashboard",{"name":"Weather: Berlin and Madrid",
        "description":"Daily observed weather, raw → staging → mart. Source: Open-Meteo ERA5. UTC."})
specs=[
    ("Observed city-days","scalar","SELECT count(*) AS city_days FROM mart.weather_daily WHERE TRUE [[AND city = {{city}}]]",{},0,0,6,3),
    ("Rainfall total (mm)","scalar","SELECT sum(precipitation) AS rainfall_mm FROM mart.weather_daily WHERE TRUE [[AND city = {{city}}]]",{},0,6,6,3),
    ("Daily temperature midpoint (C)","line","SELECT observed_date, city, temp_midpoint FROM mart.weather_daily WHERE TRUE [[AND city = {{city}}]] ORDER BY observed_date,city",
        {"graph.dimensions":["observed_date","city"],"graph.metrics":["temp_midpoint"]},3,0,12,7),
    ("Rainfall by city (mm)","bar","SELECT city,sum(precipitation) AS rainfall_mm FROM mart.weather_daily WHERE TRUE [[AND city = {{city}}]] GROUP BY city ORDER BY city",
        {"graph.dimensions":["city"],"graph.metrics":["rainfall_mm"]},0,12,12,5),
    ("Monthly weather summary","table","SELECT * FROM mart.weather_monthly WHERE TRUE [[AND city = {{city}}]] ORDER BY month,city",{},5,12,12,5)
]
existing=call("GET","card?f=all")
existing=existing.get("data",existing) if isinstance(existing,dict) else existing
cards=[]
for index,(name,display,sql,settings,row,col,width,height) in enumerate(specs):
    card=next((item for item in existing if item["name"]==name),None)
    body={"name":name,"display":display,"visualization_settings":settings,
          "dataset_query":{"database":db["id"],"type":"native","native":{"query":sql,
              "template-tags":{"city":{"id":"city","name":"city","display-name":"City","type":"text","required":False}}}}}
    card=call("PUT",f"card/{card['id']}",body) if card else call("POST","card",body)
    query=call("POST",f"card/{card['id']}/query",{"parameters":[]})
    if query.get("status")!="completed":
        raise RuntimeError(f"Query failed for {name}: {query.get('error')}")
    cards.append({"id":-(index+1),"card_id":card["id"],"row":row,"col":col,
                  "size_x":width,"size_y":height,"series":[],
                  "parameter_mappings":[{"parameter_id":"city","card_id":card["id"],
                     "target":["variable",["template-tag","city"]]}]})
    print("PASS query:",name,"rows:",len(query["data"]["rows"]))
cards.append({"id":-100,"card_id":None,"row":10,"col":0,"size_x":24,"size_y":3,"series":[],"parameter_mappings":[],
              "visualization_settings":{"virtual_card":{"display":"text"},
                 "text":"### How to read this dashboard\nSource: Open-Meteo ERA5 reanalysis. City filter applies to all charts. Temperature midpoint = (daily max + daily min)/2, not a measured daily average. Rainfall sums are for the observed period; partial months are labelled by observed_days. UTC dates; data ends seven days before collection to allow archive delay."}})
updated=call("PUT",f"dashboard/{dash['id']}",{"name":dash["name"],"dashcards":cards,
    "parameters":[{"id":"city","name":"City","slug":"city","type":"string/="}],"width":"full"})
export={"dashboard_id":dash["id"],"database_name":"Weather warehouse","cards":[
    {"name":s[0],"display":s[1],"sql":s[2],"visualization_settings":s[3]} for s in specs]}
(ROOT/"dashboard-spec.json").write_text(json.dumps(export,ensure_ascii=False,indent=2),encoding="utf-8")
print("DASHBOARD",f"{URL}/dashboard/{dash['id']}")
print("Saved reusable dashboard-spec.json without credentials")

