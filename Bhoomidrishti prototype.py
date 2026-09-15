"""
BhoomiDrishti - AI-powered land acquisition, site suitability and
pre-construction risk intelligence platform (SIH 2026 prototype).

Run it with:
    python app.py
then open http://127.0.0.1:5000

HOW THIS FILE IS ORGANISED
--------------------------
1. Setup and data loading
2. Login / roles
3. Page routes (each one renders an HTML template)
4. JSON API routes (the browser calls these with fetch())
"""

import json
import os
from functools import wraps

import pandas as pd
from flask import (Flask, jsonify, redirect, render_template, request,
                   session, url_for)

from model.risk_model import (DelayRiskModel, expected_delay_range,
                              risk_category, terrain_factor_for)
from model import rules

# ---------------------------------------------------------------------------
# 1. Setup and data loading
# ---------------------------------------------------------------------------

app = Flask(__name__)
# Only for a local prototype. In production read this from an environment variable.
app.secret_key = "bhoomidrishti-prototype-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Train the model once at startup so every request is fast.
print("BhoomiDrishti: training prototype risk model on synthetic data...")
MODEL = DelayRiskModel()
MODEL_METRICS = MODEL.train()
print("BhoomiDrishti: model ready ->", MODEL_METRICS)

with open(os.path.join(DATA_DIR, "districts.json"), "r", encoding="utf-8") as f:
    GEO = json.load(f)

DISTRICTS = {d["name"]: d for d in GEO["districts"]}
UK_DISTRICTS = [d["name"] for d in GEO["districts"] if d["state"] == "Uttarakhand"]
ALL_DISTRICTS = list(DISTRICTS.keys())
LAND_HISTORY_DEFAULT = GEO["land_history"]["_default"]

DISCLAIMER = (
    "Prototype built on synthetic and sample data. AI-generated preliminary screening only. "
    "Final foundation design, pile depth, bearing capacity and structural decisions require "
    "site-specific geotechnical investigation and qualified engineering approval."
)


def load_projects():
    """Read the sample project list and score every project with the model."""
    df = pd.read_csv(os.path.join(DATA_DIR, "projects.csv"))
    projects = []

    for row in df.to_dict(orient="records"):
        district = DISTRICTS.get(row["district"])
        terrain_text = district["terrain"] if district else "plain"

        features = {
            "compensation_pending": row["compensation_pending"],
            "legal_disputes": row["legal_disputes"],
            "pending_approvals": row["pending_approvals"],
            "documentation_completion": row["documentation_completion"],
            "possession_acquired": row["possession_acquired"],
            "rr_progress": row["rr_progress"],
            "stakeholder_responsiveness": row["stakeholder_responsiveness"],
            "affected_families": row["affected_families"],
            "land_area": row["land_area"],
            "terrain_factor": terrain_factor_for(terrain_text),
        }

        probability = MODEL.predict(features)
        factors = MODEL.explain(features, top_n=3)

        row["delay_probability"] = probability
        row["risk_level"] = risk_category(probability)
        row["expected_delay"] = expected_delay_range(probability)
        row["top_factors"] = factors
        row["model_main_factor"] = factors[0]["label"] if factors else "-"
        projects.append(row)

    projects.sort(key=lambda p: p["delay_probability"], reverse=True)
    return projects


PROJECTS = load_projects()


def build_alerts(projects):
    """Turn the riskiest projects into actionable alert cards."""
    alerts = []
    for project in projects:
        probability = project["delay_probability"]
        if probability < 55:
            continue

        issues = []
        if project["compensation_pending"] >= 50:
            issues.append("compensation pending")
        if project["legal_disputes"] >= 4:
            issues.append("legal disputes")
        if project["pending_approvals"] >= 4:
            issues.append("pending approvals")
        if project["possession_acquired"] <= 45:
            issues.append("possession not taken")
        if not issues:
            issues.append(project["main_risk_factor"].lower())

        district = DISTRICTS.get(project["district"])
        if district and district["landslide"] >= 75:
            issues.append("high landslide exposure")
        if district and district["flood"] >= 75:
            issues.append("high flood exposure")

        alerts.append({
            "severity": "CRITICAL" if probability >= 75 else "HIGH",
            "project_id": project["project_id"],
            "project": project["project_name"],
            "location": f"{project['district']}, {project['state']}",
            "delay_probability": probability,
            "issue": " + ".join(issues[:3]),
            "recommended": (
                "Immediate intervention: convene the empowered committee this week"
                if probability >= 75 else
                "Escalate to the monthly review and assign a nodal officer per issue"
            ),
        })
    return alerts


ALERTS = build_alerts(PROJECTS)

USERS = {
    "admin": {"password": "admin123", "role": "Administrator", "name": "System Administrator"},
    "officer": {"password": "officer123", "role": "Government Officer", "name": "District Officer"},
    "contractor": {"password": "contractor123", "role": "Contractor", "name": "Site Contractor"},
    "manager": {"password": "manager123", "role": "Project Manager", "name": "Project Manager"},
}

# Which sidebar sections each role is meant to focus on. Every role can open
# every page in this prototype; the badge just shows the intended scope.
ROLE_FOCUS = {
    "Administrator": ["dashboard", "prediction", "projects", "alerts", "data_intelligence"],
    "Government Officer": ["dashboard", "prediction", "study_area", "land_history", "alerts"],
    "Contractor": ["before_build", "terrain", "geotechnical", "contractor", "comparison"],
    "Project Manager": ["projects", "prediction", "recommendations", "alerts", "comparison"],
}


# ---------------------------------------------------------------------------
# 2. Login / roles
# ---------------------------------------------------------------------------

def login_required(view):
    """Redirect to the login page if nobody is signed in."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_globals():
    """Values available inside every template without passing them each time."""
    return {
        "app_name": "BhoomiDrishti",
        "tagline": "Know the Land Before You Build.",
        "disclaimer": DISCLAIMER,
        "current_user": session.get("user"),
        "current_role": session.get("role"),
        "role_focus": ROLE_FOCUS.get(session.get("role"), []),
    }


@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        account = USERS.get(username)
        if account and account["password"] == password:
            session["user"] = account["name"]
            session["role"] = account["role"]
            return redirect(url_for("dashboard"))
        error = "Username or password did not match. Try admin / admin123."
    return render_template("login.html", error=error, demo_users=USERS)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# 3. Page routes
# ---------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", page="dashboard",
                           metrics=MODEL_METRICS)


@app.route("/prediction")
@login_required
def prediction():
    return render_template("prediction.html", page="prediction",
                           project_types=rules.PROJECT_TYPES,
                           districts=ALL_DISTRICTS,
                           metrics=MODEL_METRICS)


@app.route("/projects")
@login_required
def projects_page():
    return render_template("projects.html", page="projects", projects=PROJECTS)


@app.route("/before-build")
@login_required
def before_build():
    return render_template("before_build.html", page="before_build",
                           project_types=rules.PROJECT_TYPES,
                           districts=ALL_DISTRICTS, uk_districts=UK_DISTRICTS)


@app.route("/study-area")
@login_required
def study_area():
    return render_template("study_area.html", page="study_area",
                           uk_districts=UK_DISTRICTS)


@app.route("/land-history")
@login_required
def land_history():
    return render_template("land_history.html", page="land_history",
                           projects=PROJECTS, history=LAND_HISTORY_DEFAULT)


@app.route("/planning")
@login_required
def planning():
    return render_template("planning.html", page="planning",
                           project_types=rules.PROJECT_TYPES,
                           districts=ALL_DISTRICTS)


@app.route("/terrain")
@login_required
def terrain():
    return render_template("terrain.html", page="terrain",
                           districts=ALL_DISTRICTS, uk_districts=UK_DISTRICTS)


@app.route("/disaster")
@login_required
def disaster():
    return render_template("disaster.html", page="disaster",
                           districts=ALL_DISTRICTS, uk_districts=UK_DISTRICTS)


@app.route("/geotechnical")
@login_required
def geotechnical():
    return render_template("geotechnical.html", page="geotechnical",
                           soil_types=rules.SOIL_TYPES)


@app.route("/contractor")
@login_required
def contractor():
    return render_template("contractor.html", page="contractor", projects=PROJECTS)


@app.route("/comparison")
@login_required
def comparison():
    return render_template("comparison.html", page="comparison",
                           districts=ALL_DISTRICTS,
                           project_types=rules.PROJECT_TYPES)


@app.route("/map")
@login_required
def risk_map():
    return render_template("map.html", page="map")


@app.route("/recommendations")
@login_required
def recommendations():
    return render_template("recommendations.html", page="recommendations",
                           projects=PROJECTS)


@app.route("/alerts")
@login_required
def alerts_page():
    return render_template("alerts.html", page="alerts", alerts=ALERTS)


@app.route("/assistant")
@login_required
def assistant():
    return render_template("assistant.html", page="assistant")


@app.route("/data-intelligence")
@login_required
def data_intelligence():
    sources = [
        {"name": "Land records (Bhulekh / revenue department)", "type": "Land Records",
         "status": "Future integration", "detail": "Khasra, khatauni and mutation status per survey number"},
        {"name": "Project monitoring records (departmental MIS)", "type": "Project Records",
         "status": "Prototype", "detail": "Stage, physical progress and acquisition status feeds"},
        {"name": "GSI landslide susceptibility", "type": "Disaster Data",
         "status": "Future integration", "detail": "Published susceptibility mapping for hill districts"},
        {"name": "CWC / SDMA flood and disaster reports", "type": "Disaster Data",
         "status": "Future integration", "detail": "Historical flood levels and incident records"},
        {"name": "IMD rainfall observations", "type": "Weather Data",
         "status": "Future integration", "detail": "Rainfall intensity and extreme-event history"},
        {"name": "Bhuvan / SRTM elevation model", "type": "GIS Data",
         "status": "Future integration", "detail": "DEM-derived slope, aspect and elevation"},
        {"name": "OpenStreetMap base tiles", "type": "GIS Data",
         "status": "Connected", "detail": "Live base map used on the GIS Risk Map page"},
        {"name": "Prototype sample dataset", "type": "Project Records",
         "status": "Connected", "detail": "projects.csv and districts.json shipped with this prototype"},
    ]
    return render_template("data_intelligence.html", page="data_intelligence",
                           sources=sources)


@app.route("/resources")
@login_required
def resources():
    return render_template("resources.html", page="resources")


@app.route("/about")
@login_required
def about():
    return render_template("about.html", page="about", metrics=MODEL_METRICS)


# ---------------------------------------------------------------------------
# 4. JSON API routes
# ---------------------------------------------------------------------------

@app.route("/api/projects")
@login_required
def api_projects():
    return jsonify(PROJECTS)


@app.route("/api/dashboard")
@login_required
def api_dashboard():
    """All the numbers and chart series the dashboard needs, in one call."""
    total = len(PROJECTS)
    levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    distribution = {level: 0 for level in levels}
    for project in PROJECTS:
        distribution[project["risk_level"]] += 1

    by_state = {}
    by_district = {}
    by_stage = {}
    for project in PROJECTS:
        by_state.setdefault(project["state"], []).append(project["delay_probability"])
        by_district.setdefault(project["district"], []).append(project["delay_probability"])
        by_stage[project["stage"]] = by_stage.get(project["stage"], 0) + 1

    def average_map(source):
        return {key: round(sum(values) / len(values), 1) for key, values in source.items()}

    state_avg = dict(sorted(average_map(by_state).items(), key=lambda kv: kv[1], reverse=True))
    district_avg = dict(sorted(average_map(by_district).items(),
                               key=lambda kv: kv[1], reverse=True)[:10])

    # Aggregate the model's local explanations into the portfolio-wide drivers.
    drivers = {}
    for project in PROJECTS:
        for factor in project["top_factors"]:
            drivers[factor["label"]] = drivers.get(factor["label"], 0) + factor["impact_points"]
    top_drivers = dict(sorted(drivers.items(), key=lambda kv: kv[1], reverse=True)[:6])
    top_drivers = {key: round(value, 1) for key, value in top_drivers.items()}

    # Illustrative monthly trend: portfolio average nudged by a sample curve.
    average = sum(p["delay_probability"] for p in PROJECTS) / total
    shape = [-7, -5, -2, 0, 2, 3, 5, 6, 4, 3, 1, 0]
    months = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar",
              "Apr", "May", "Jun", "Jul", "Aug", "Sep"]
    trend = [round(max(0, min(100, average + delta)), 1) for delta in shape]

    return jsonify({
        "kpi": {
            "total_projects": total,
            "high_risk": distribution["HIGH"],
            "critical": distribution["CRITICAL"],
            "avg_delay_probability": round(average, 1),
            "needs_intervention": sum(1 for p in PROJECTS if p["delay_probability"] >= 65),
            "land_area": round(sum(p["land_area"] for p in PROJECTS), 1),
            "affected_families": int(sum(p["affected_families"] for p in PROJECTS)),
        },
        "risk_distribution": distribution,
        "state_risk": state_avg,
        "district_risk": district_avg,
        "stage_distribution": by_stage,
        "top_drivers": top_drivers,
        "trend": {"labels": months, "values": trend},
        "critical_projects": [
            {
                "project_id": p["project_id"], "project_name": p["project_name"],
                "state": p["state"], "district": p["district"],
                "project_type": p["project_type"], "risk_level": p["risk_level"],
                "delay_probability": p["delay_probability"],
                "main_risk_factor": p["main_risk_factor"],
                "model_main_factor": p["model_main_factor"],
            }
            for p in PROJECTS if p["delay_probability"] >= 55
        ],
        "model_metrics": MODEL_METRICS,
    })


@app.route("/api/predict", methods=["POST"])
@login_required
def api_predict():
    """Predict land acquisition delay risk and explain the prediction."""
    form = request.get_json(silent=True) or {}
    district_name = form.get("district")
    district = DISTRICTS.get(district_name)
    terrain_text = district["terrain"] if district else form.get("terrain", "plain")

    def number(key, default=0):
        try:
            return float(form.get(key, default))
        except (TypeError, ValueError):
            return float(default)

    features = {
        "compensation_pending": number("compensation_pending", 40),
        "legal_disputes": number("legal_disputes", 0),
        "pending_approvals": number("pending_approvals", 0),
        "documentation_completion": number("documentation_completion", 80),
        "possession_acquired": number("possession_acquired", 70),
        "rr_progress": number("rr_progress", 70),
        "stakeholder_responsiveness": number("stakeholder_responsiveness", 70),
        "affected_families": number("affected_families", 100),
        "land_area": number("land_area", 50),
        "terrain_factor": terrain_factor_for(terrain_text),
    }

    probability = MODEL.predict(features)
    category = risk_category(probability)
    factors = MODEL.explain(features)

    return jsonify({
        "delay_probability": probability,
        "risk_category": category,
        "expected_delay": expected_delay_range(probability),
        "factors": factors,
        "explanation": rules.explanation_sentence(category, factors),
        "recommendations": rules.acquisition_recommendations(features, factors),
        "global_importance": MODEL.global_importance,
        "model_metrics": MODEL_METRICS,
        "inputs_used": features,
        "project_type": form.get("project_type", "Road"),
        "district": district_name,
        "state": district["state"] if district else form.get("state", "-"),
        "disclaimer": DISCLAIMER,
    })


def assess_district(district_name, project_type, land_area, affected_families):
    """Shared helper used by Before You Build and Site Comparison."""
    district = DISTRICTS.get(district_name)
    if district is None:
        return None

    features = {
        "compensation_pending": 45, "legal_disputes": 2, "pending_approvals": 2,
        "documentation_completion": 75, "possession_acquired": 60, "rr_progress": 65,
        "stakeholder_responsiveness": 68, "affected_families": affected_families,
        "land_area": land_area, "terrain_factor": terrain_factor_for(district["terrain"]),
    }
    acquisition_probability = MODEL.predict(features)

    result = rules.site_assessment(district, project_type, land_area,
                                   affected_families, acquisition_probability)
    result["acquisition_probability"] = acquisition_probability
    result["acquisition_note"] = (
        "Acquisition risk uses the Random Forest model with typical mid-stage "
        "indicator values; enter your real figures on the Risk Prediction page."
    )
    return result


@app.route("/api/site-assess", methods=["POST"])
@login_required
def api_site_assess():
    form = request.get_json(silent=True) or {}
    result = assess_district(
        form.get("district", "Chamoli"),
        form.get("project_type", "Road"),
        float(form.get("land_area", 80) or 80),
        float(form.get("affected_families", 200) or 200),
    )
    if result is None:
        return jsonify({"error": "Unknown district"}), 400
    return jsonify(result)


@app.route("/api/district/<name>")
@login_required
def api_district(name):
    district = DISTRICTS.get(name)
    if district is None:
        return jsonify({"error": "Unknown district"}), 404
    return jsonify({
        "district": district,
        "terrain": rules.terrain_analysis(district),
        "hazards": rules.disaster_screening(district),
    })


@app.route("/api/geotech", methods=["POST"])
@login_required
def api_geotech():
    form = request.get_json(silent=True) or {}
    result = rules.geotechnical_screening(form)
    result["recommendations"] = [
        {"priority": result["investigation_priority"],
         "trigger": f"Investigation priority {result['investigation_priority']}",
         "action": f"Plan boreholes to {result['recommended_investigation_depth']} "
                   f"with laboratory testing before foundation design"}
    ]
    if result["groundwater_concern"] >= 55:
        result["recommendations"].append({
            "priority": "HIGH", "trigger": "Shallow groundwater",
            "action": "Plan dewatering, shoring and excavation support; review uplift conditions"})
    if result["settlement_risk"] >= 55:
        result["recommendations"].append({
            "priority": "HIGH", "trigger": "Elevated settlement indicator",
            "action": "Investigate compressible layers and consider ground improvement options"})
    return jsonify(result)


@app.route("/api/compare", methods=["POST"])
@login_required
def api_compare():
    """Score up to three candidate sites and name the best-scoring one."""
    form = request.get_json(silent=True) or {}
    project_type = form.get("project_type", "Road")
    land_area = float(form.get("land_area", 80) or 80)
    families = float(form.get("affected_families", 200) or 200)
    names = form.get("sites", ["Chamoli", "Dehradun", "Haridwar"])

    sites = []
    for index, name in enumerate(names[:3]):
        result = assess_district(name, project_type, land_area, families)
        if result:
            result["label"] = f"Site {chr(65 + index)}"
            sites.append(result)

    if not sites:
        return jsonify({"error": "No valid sites"}), 400

    best = max(sites, key=lambda s: s["suitability"])
    return jsonify({
        "sites": sites,
        "parameters": [row["name"] for row in sites[0]["rows"]],
        "recommended": {
            "label": best["label"], "district": best["district"],
            "state": best["state"], "suitability": best["suitability"],
            "why": best["verdict"],
        },
        "caveat": "Subject to detailed engineering, environmental and statutory investigation.",
    })


@app.route("/api/map-projects")
@login_required
def api_map_projects():
    return jsonify([
        {
            "project_id": p["project_id"], "project_name": p["project_name"],
            "state": p["state"], "district": p["district"],
            "project_type": p["project_type"], "risk_level": p["risk_level"],
            "delay_probability": p["delay_probability"], "land_area": p["land_area"],
            "affected_families": int(p["affected_families"]),
            "main_risk_factor": p["main_risk_factor"],
            "lat": p["latitude"], "lon": p["longitude"],
        }
        for p in PROJECTS
    ])


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    form = request.get_json(silent=True) or {}
    reply = rules.answer_question(form.get("question", ""), form.get("language", "en"))
    reply["disclaimer"] = "BhoomiAI gives screening-level guidance only, not engineering approval."
    return jsonify(reply)


@app.route("/api/alerts")
@login_required
def api_alerts():
    return jsonify(ALERTS)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
