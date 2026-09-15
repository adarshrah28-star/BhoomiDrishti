"""Exercise every route and API so we know the app really runs."""
import json
from app import app

app.config["TESTING"] = True
client = app.test_client()

# Unauthenticated should redirect
r = client.get("/dashboard")
assert r.status_code == 302, r.status_code

# Login
r = client.post("/", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
assert r.status_code == 200 and b"Executive dashboard" in r.data

pages = ["/dashboard","/prediction","/projects","/before-build","/study-area","/land-history",
         "/planning","/terrain","/disaster","/geotechnical","/contractor","/comparison","/map",
         "/recommendations","/alerts","/assistant","/data-intelligence","/resources","/about"]
for page in pages:
    r = client.get(page)
    assert r.status_code == 200, (page, r.status_code)
    assert b"Traceback" not in r.data
    print("OK page", page, len(r.data))

r = client.get("/api/dashboard"); d = r.get_json()
assert r.status_code == 200
print("KPI", d["kpi"])
print("critical count", len(d["critical_projects"]), "drivers", list(d["top_drivers"])[:3])

r = client.post("/api/predict", json={
    "district":"Chamoli","project_type":"Highway","land_area":148.5,"affected_families":412,
    "compensation_pending":78,"legal_disputes":9,"pending_approvals":6,
    "documentation_completion":54,"possession_acquired":31,"rr_progress":38,
    "stakeholder_responsiveness":42})
p = r.get_json()
print("PREDICT", p["delay_probability"], p["risk_category"], p["expected_delay"])
print("  ", p["explanation"])
print("  factors", [(f["label"], f["percent"]) for f in p["factors"][:3]])
print("  recos", len(p["recommendations"]))

r = client.post("/api/site-assess", json={"district":"Chamoli","project_type":"Road","land_area":95,"affected_families":260})
s = r.get_json()
print("SITE", s["suitability"], s["suitability_band"], [(x["name"], x["value"]) for x in s["rows"]])

r = client.post("/api/geotech", json={"soil_type":"Silty soil","spt_n":11,"groundwater_m":2.5,
  "rock_depth_m":14,"moisture":26,"cohesion":18,"friction_angle":26,"borehole_data":"no"})
g = r.get_json()
print("GEOTECH", g["stability"], g["settlement_risk"], g["groundwater_concern"], g["investigation_priority"], g["recommended_investigation_depth"])

r = client.post("/api/compare", json={"sites":["Chamoli","Nainital","Dehradun"],"project_type":"Highway","land_area":110,"affected_families":280})
c = r.get_json()
print("COMPARE", [(x["label"], x["district"], x["suitability"]) for x in c["sites"]], "->", c["recommended"]["district"])

for q, lang in [("Can AI determine pile depth?","en"),("major causes of land acquisition delay","en"),
                ("landslide","hi"),("blah blah","en")]:
    a = client.post("/api/chat", json={"question":q,"language":lang}).get_json()
    print("CHAT", lang, repr(q), "->", a["matched"], a["answer"][:60])

r = client.get("/api/map-projects"); print("MAP projects", len(r.get_json()))
r = client.get("/api/alerts"); print("ALERTS", len(r.get_json()))
r = client.get("/api/district/Chamoli"); print("DISTRICT ok", r.get_json()["terrain"]["construction_difficulty"])
print("\nALL CHECKS PASSED")
