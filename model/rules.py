"""
BhoomiDrishti - transparent rule engine.

Everything in this file is deliberately rule-based (not machine learning) so
that every number shown on screen can be traced back to an explicit formula.
That matters for a decision-support tool: a reviewer must be able to ask
"why 72?" and get an answer.

All thresholds here are illustrative prototype values.
"""

# ---------------------------------------------------------------------------
# Project type sensitivities
# ---------------------------------------------------------------------------
# How much each project type cares about each hazard (1.0 = normal weight).
PROJECT_SENSITIVITY = {
    "Road":       {"slope": 1.2, "landslide": 1.3, "flood": 1.0, "quake": 0.9, "geotech": 1.0},
    "Highway":    {"slope": 1.2, "landslide": 1.3, "flood": 1.1, "quake": 0.9, "geotech": 1.1},
    "Expressway": {"slope": 1.3, "landslide": 1.3, "flood": 1.2, "quake": 0.9, "geotech": 1.1},
    "Bridge":     {"slope": 1.1, "landslide": 1.2, "flood": 1.4, "quake": 1.3, "geotech": 1.4},
    "Tunnel":     {"slope": 1.0, "landslide": 1.1, "flood": 0.8, "quake": 1.2, "geotech": 1.5},
    "Building":   {"slope": 1.1, "landslide": 1.1, "flood": 1.2, "quake": 1.3, "geotech": 1.2},
    "Industrial": {"slope": 1.2, "landslide": 1.0, "flood": 1.3, "quake": 1.1, "geotech": 1.2},
    "Urban":      {"slope": 1.0, "landslide": 1.0, "flood": 1.3, "quake": 1.2, "geotech": 1.1},
    "Rail":       {"slope": 1.3, "landslide": 1.2, "flood": 1.1, "quake": 1.0, "geotech": 1.2},
    "Dam":        {"slope": 1.2, "landslide": 1.3, "flood": 1.2, "quake": 1.4, "geotech": 1.5},
}

PROJECT_TYPES = list(PROJECT_SENSITIVITY.keys())


def band(value):
    """Turn any 0-100 risk number into a four-level label."""
    if value >= 75:
        return "CRITICAL"
    if value >= 55:
        return "HIGH"
    if value >= 35:
        return "MEDIUM"
    return "LOW"


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def weigh(base, weight):
    """Apply a project-type sensitivity without letting scores pile up at 100.

    Multiplying (88 x 1.3) would clip at 100 and lose all detail at the top of
    the scale. Instead we move the score a fraction of the way towards 100 (or
    towards 0 for a weight below 1), so ordering is preserved everywhere.
    """
    if weight >= 1:
        return clamp(base + (100 - base) * (weight - 1) * 0.55)
    return clamp(base * (1 - (1 - weight) * 0.55))


# ---------------------------------------------------------------------------
# Terrain
# ---------------------------------------------------------------------------

def terrain_analysis(district):
    """Derive terrain difficulty from elevation, slope and accessibility."""
    slope = district["avg_slope_deg"]
    elevation = district["elevation_m"]
    access = district["accessibility"]

    # Slope is the dominant driver of construction difficulty in hill terrain.
    slope_risk = clamp(slope / 45 * 100)
    elevation_risk = clamp(elevation / 3000 * 100)
    access_risk = clamp(100 - access)

    difficulty = clamp(0.55 * slope_risk + 0.20 * elevation_risk + 0.25 * access_risk)

    # Slope stability also depends on how well water drains away.
    stability_risk = clamp(0.65 * slope_risk + 0.35 * (100 - district["drainage"]))

    return {
        "elevation_m": elevation,
        "avg_slope_deg": slope,
        "terrain": district["terrain"],
        "soil": district["soil"],
        "accessibility": access,
        "slope_risk": round(slope_risk),
        "construction_difficulty": round(difficulty),
        "construction_difficulty_band": band(difficulty),
        "slope_stability_risk": round(stability_risk),
        "slope_stability_band": band(stability_risk),
        "cut_slope_note": (
            "Deep cut slopes likely; benching and retaining structures expected"
            if slope >= 25 else
            "Moderate cutting expected; standard side-slope protection likely"
            if slope >= 12 else
            "Minimal cutting expected in near-level ground"
        ),
    }


# ---------------------------------------------------------------------------
# Disaster screening
# ---------------------------------------------------------------------------

def disaster_screening(district):
    """Preliminary disaster risk screening - NOT a real-time forecast."""
    items = [
        ("Landslide", district["landslide"]),
        ("Flood", district["flood"]),
        ("Flash flood", district["flash_flood"]),
        ("Earthquake vulnerability", district["earthquake"]),
        ("Cloudburst exposure", district["cloudburst"]),
        ("Extreme rainfall", district["extreme_rainfall"]),
    ]
    hazards = [{"name": n, "value": v, "band": band(v)} for n, v in items]
    composite = round(sum(v for _, v in items) / len(items))
    return {
        "hazards": hazards,
        "composite": composite,
        "composite_band": band(composite),
        "seismic_zone": district["seismic_zone"],
        "disclaimer": (
            "Preliminary disaster risk screening based on prototype sample data. "
            "Not a forecast and not a substitute for NDMA, GSI or CWC hazard assessment."
        ),
    }


# ---------------------------------------------------------------------------
# Geotechnical screening
# ---------------------------------------------------------------------------

GEOTECH_DISCLAIMER = (
    "Preliminary screening indicators only. Final foundation design, pile depth, "
    "bearing capacity and structural decisions require site-specific geotechnical "
    "investigation and qualified engineering approval."
)

SOIL_QUALITY = {
    "Rock": 92, "Weathered rock": 74, "Gravel": 78, "Dense sand": 70,
    "Loose sand": 40, "Silty soil": 46, "Stiff clay": 62,
    "Soft clay": 26, "Fill / made ground": 22, "Black cotton soil": 34,
}

SOIL_TYPES = list(SOIL_QUALITY.keys())


def geotechnical_screening(form):
    """Score preliminary soil stability from screening-level inputs.

    Inputs are the kind of values available early: a soil description, an SPT
    N-value, groundwater depth, depth to rock, moisture, cohesion and friction
    angle. We combine them into indicator scores - never a design value.
    """
    soil_type = form.get("soil_type", "Silty soil")
    spt_n = float(form.get("spt_n", 12))
    groundwater_m = float(form.get("groundwater_m", 4))
    rock_depth_m = float(form.get("rock_depth_m", 12))
    moisture = float(form.get("moisture", 22))
    cohesion = float(form.get("cohesion", 20))
    friction_angle = float(form.get("friction_angle", 28))
    has_borehole = str(form.get("borehole_data", "no")).lower() in ("yes", "true", "1", "on")

    soil_score = SOIL_QUALITY.get(soil_type, 45)

    # Each indicator is normalised to a 0-100 "favourable" score.
    spt_score = clamp(spt_n / 50 * 100)
    water_score = clamp(groundwater_m / 10 * 100)          # deeper water is better
    rock_score = clamp(100 - rock_depth_m / 30 * 100)      # shallow rock is better
    moisture_score = clamp(100 - abs(moisture - 18) * 3)   # very dry or very wet is worse
    strength_score = clamp(0.5 * clamp(cohesion / 60 * 100)
                           + 0.5 * clamp(friction_angle / 45 * 100))

    stability = round(
        0.28 * soil_score + 0.24 * spt_score + 0.16 * water_score
        + 0.10 * rock_score + 0.08 * moisture_score + 0.14 * strength_score
    )

    settlement_risk = clamp(round(100 - (0.5 * spt_score + 0.3 * soil_score + 0.2 * strength_score)))
    excavation_risk = clamp(round(0.5 * (100 - water_score) + 0.3 * (100 - soil_score) + 0.2 * rock_score))
    groundwater_concern = clamp(round(100 - water_score))

    # Very rough indicative range only, clearly flagged as non-design.
    low_capacity = max(40, round(spt_n * 9 + soil_score * 1.2))
    high_capacity = low_capacity + max(60, round(spt_n * 6))

    priority_score = (settlement_risk + groundwater_concern + (0 if has_borehole else 25)) / 2
    priority = band(clamp(priority_score))

    return {
        "inputs": {
            "soil_type": soil_type, "spt_n": spt_n, "groundwater_m": groundwater_m,
            "rock_depth_m": rock_depth_m, "moisture": moisture, "cohesion": cohesion,
            "friction_angle": friction_angle, "borehole_data": has_borehole,
        },
        "stability": stability,
        "stability_band": band(100 - stability),
        "settlement_risk": settlement_risk,
        "settlement_band": band(settlement_risk),
        "excavation_risk": excavation_risk,
        "excavation_band": band(excavation_risk),
        "groundwater_concern": groundwater_concern,
        "groundwater_band": band(groundwater_concern),
        "indicative_bearing_range": f"{low_capacity}-{high_capacity} kPa (indicative screening range, not a design value)",
        "recommended_investigation_depth": (
            "20-30 m" if rock_depth_m > 20 else "15-20 m" if rock_depth_m > 10 else "10-15 m"
        ),
        "investigation_priority": priority,
        "indicators": [
            {"name": "Soil description", "score": round(soil_score)},
            {"name": "SPT N-value", "score": round(spt_score)},
            {"name": "Groundwater depth", "score": round(water_score)},
            {"name": "Depth to rock", "score": round(rock_score)},
            {"name": "Moisture condition", "score": round(moisture_score)},
            {"name": "Shear strength inputs", "score": round(strength_score)},
        ],
        "disclaimer": GEOTECH_DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# Before You Build - full site assessment
# ---------------------------------------------------------------------------

def site_assessment(district, project_type, land_area, affected_families,
                    acquisition_probability=None):
    """Combine terrain, hazards, geotechnical proxy and acquisition risk."""
    weights = PROJECT_SENSITIVITY.get(project_type, PROJECT_SENSITIVITY["Road"])
    terrain = terrain_analysis(district)
    hazards = disaster_screening(district)

    landslide = weigh(district["landslide"], weights["landslide"])
    flood = weigh(district["flood"], weights["flood"])
    quake = weigh(district["earthquake"], weights["quake"])
    terrain_risk = weigh(terrain["construction_difficulty"], weights["slope"])

    # Geotechnical proxy when no borehole data exists yet: soil quality,
    # slope and groundwater/drainage conditions.
    soil_score = SOIL_QUALITY.get(district["soil"].split()[0].capitalize(), 48)
    geotech_risk = weigh(0.45 * (100 - soil_score)
                         + 0.30 * terrain["slope_risk"]
                         + 0.25 * (100 - district["drainage"]), weights["geotech"])

    # Bigger footprint and more displaced families means harder acquisition.
    if acquisition_probability is None:
        acquisition_risk = clamp(0.5 * clamp(land_area / 300 * 100)
                                 + 0.5 * clamp(affected_families / 700 * 100))
    else:
        acquisition_risk = clamp(acquisition_probability)

    environmental_risk = clamp(0.4 * terrain["slope_risk"]
                               + 0.3 * clamp(district["elevation_m"] / 2500 * 100)
                               + 0.3 * clamp(land_area / 300 * 100))

    construction_risk = clamp(round(
        0.30 * terrain_risk + 0.24 * landslide + 0.16 * flood
        + 0.16 * geotech_risk + 0.14 * quake
    ))

    overall_risk = (0.22 * terrain_risk + 0.20 * landslide + 0.14 * flood
                    + 0.12 * quake + 0.16 * acquisition_risk
                    + 0.10 * geotech_risk + 0.06 * environmental_risk)
    suitability = round(clamp(100 - overall_risk))

    rows = [
        {"name": "Terrain risk", "value": round(terrain_risk), "band": band(terrain_risk)},
        {"name": "Landslide risk", "value": round(landslide), "band": band(landslide)},
        {"name": "Flood risk", "value": round(flood), "band": band(flood)},
        {"name": "Earthquake risk", "value": round(quake), "band": band(quake)},
        {"name": "Land acquisition risk", "value": round(acquisition_risk), "band": band(acquisition_risk)},
        {"name": "Preliminary geotechnical risk", "value": round(geotech_risk), "band": band(geotech_risk)},
        {"name": "Environmental risk", "value": round(environmental_risk), "band": band(environmental_risk)},
        {"name": "Construction risk", "value": round(construction_risk), "band": band(construction_risk)},
    ]

    verdict = (
        "Site looks comparatively favourable, subject to detailed investigation"
        if suitability >= 70 else
        "Site is workable but needs risk mitigation built into the design and schedule"
        if suitability >= 50 else
        "Site carries serious constraints; examine alternative locations or alignments"
    )

    return {
        "district": district["name"],
        "state": district["state"],
        "project_type": project_type,
        "land_area": land_area,
        "affected_families": affected_families,
        "suitability": suitability,
        "suitability_band": band(100 - suitability),
        "verdict": verdict,
        "rows": rows,
        "terrain": terrain,
        "hazards": hazards,
        "seismic_zone": district["seismic_zone"],
        "recommendations": recommendations_for(rows, district),
        "disclaimer": GEOTECH_DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# Recommendation engine
# ---------------------------------------------------------------------------

# Each rule: risk name -> (threshold, action, why)
RECOMMENDATION_RULES = [
    ("Landslide risk", 55,
     "Commission a detailed slope stability and geological investigation along the alignment",
     "Steep slopes with a landslide history dominate the risk profile here"),
    ("Terrain risk", 55,
     "Plan hill-cutting volumes, retaining structures and haul-road access before mobilisation",
     "Terrain difficulty drives both cost and schedule in mountain projects"),
    ("Flood risk", 55,
     "Review cross-drainage, culvert capacity and high-flood-level clearance",
     "Flood exposure at this location is above the screening threshold"),
    ("Earthquake risk", 55,
     "Apply the correct BIS seismic zone factor and review liquefaction potential",
     "The site falls in a high seismic exposure band"),
    ("Preliminary geotechnical risk", 50,
     "Programme additional boreholes and laboratory testing before foundation design",
     "Screening indicators suggest weak or variable subsurface conditions"),
    ("Land acquisition risk", 50,
     "Start acquisition and R&R activity in parallel with the DPR, not after it",
     "Land area and affected families indicate a long acquisition cycle"),
    ("Environmental risk", 55,
     "Begin forest, wildlife and environmental clearance screening early",
     "Elevation and footprint suggest clearance processes may be on the critical path"),
    ("Construction risk", 60,
     "Build weather windows and slope-failure contingency into the construction programme",
     "Combined hazard and terrain exposure raises execution risk"),
]


def recommendations_for(rows, district=None):
    """Produce actions from the risk rows. Always returns at least one item."""
    values = {row["name"]: row["value"] for row in rows}
    out = []
    for name, threshold, action, why in RECOMMENDATION_RULES:
        value = values.get(name)
        if value is not None and value >= threshold:
            out.append({
                "priority": "HIGH" if value >= 70 else "MEDIUM",
                "trigger": f"{name} at {value}",
                "action": action,
                "why": why,
            })

    if district and district["accessibility"] < 50:
        out.append({
            "priority": "MEDIUM",
            "trigger": f"Accessibility at {district['accessibility']}",
            "action": "Plan material logistics, storage yards and an all-weather access route",
            "why": "Remote access limits working days and delivery reliability",
        })

    if not out:
        out.append({
            "priority": "LOW",
            "trigger": "No threshold crossed",
            "action": "Proceed to detailed survey and statutory investigation",
            "why": "Screening indicators are within the prototype's comfortable range",
        })
    return out


def acquisition_recommendations(inputs, factors):
    """Actions driven by the land-acquisition inputs and model explanation."""
    out = []

    def add(priority, trigger, action):
        out.append({"priority": priority, "trigger": trigger, "action": action})

    if float(inputs.get("compensation_pending", 0)) >= 50:
        add("HIGH", f"Compensation pending {inputs['compensation_pending']}%",
            "Prioritise compensation verification and disbursement; publish a beneficiary-wise tracker")
    if float(inputs.get("legal_disputes", 0)) >= 4:
        add("HIGH", f"{int(float(inputs['legal_disputes']))} active legal disputes",
            "Create a dedicated legal-resolution worklist with a nodal officer per case")
    if float(inputs.get("pending_approvals", 0)) >= 3:
        add("HIGH", f"{int(float(inputs['pending_approvals']))} pending approvals",
            "Escalate overdue approvals to the empowered committee with dated follow-up")
    if float(inputs.get("documentation_completion", 100)) <= 75:
        add("MEDIUM", f"Documentation at {inputs['documentation_completion']}%",
            "Run a document completeness audit covering mutation, khasra and title records")
    if float(inputs.get("possession_acquired", 100)) <= 60:
        add("HIGH", f"Possession at {inputs['possession_acquired']}%",
            "Sequence work to the encumbrance-free stretches while possession is pursued")
    if float(inputs.get("rr_progress", 100)) <= 60:
        add("MEDIUM", f"R&R progress at {inputs['rr_progress']}%",
            "Accelerate rehabilitation and resettlement entitlements ahead of possession")
    if float(inputs.get("stakeholder_responsiveness", 100)) <= 55:
        add("MEDIUM", f"Stakeholder responsiveness at {inputs['stakeholder_responsiveness']}%",
            "Hold structured village-level consultations and publish a grievance redressal calendar")

    if not out:
        add("LOW", "All acquisition indicators healthy",
            "Maintain the current monitoring cadence and monthly reporting")
    return out


def explanation_sentence(category, factors):
    """One plain-language line summarising the model output."""
    if not factors:
        return f"The project is classified as {category} risk with no single dominant driver."
    top = [f["label"].lower() for f in factors[:2]]
    if len(top) == 1:
        return f"The project is classified as {category} risk primarily because of {top[0]}."
    return (f"The project is classified as {category} risk primarily because of "
            f"{top[0]} and {top[1]}.")


# ---------------------------------------------------------------------------
# BhoomiAI - rule-based assistant
# ---------------------------------------------------------------------------
# Each entry: keywords -> English answer, Hindi answer.
# To connect a real LLM later, replace the body of answer_question() with an
# API call and keep this table as the offline fallback.

KNOWLEDGE_BASE = [
    (["pile", "pile depth", "foundation depth", "bearing capacity", "structural design"],
     "No. BhoomiDrishti cannot determine pile depth, foundation depth, bearing capacity or "
     "reinforcement. Those are design outputs that need borehole data, laboratory testing and "
     "a qualified geotechnical engineer's certification. What this platform does is screening: "
     "it flags where the subsurface looks risky and suggests an investigation depth range and "
     "priority, so you know where to spend investigation budget first.",
     "\u0928\u0939\u0940\u0902\u0964 BhoomiDrishti \u092a\u093e\u0907\u0932 \u0917\u0939\u0930\u093e\u0908, \u0928\u0940\u0902\u0935 \u0915\u0940 \u0917\u0939\u0930\u093e\u0908 \u092f\u093e \u092c\u0947\u092f\u0930\u093f\u0902\u0917 \u0915\u0947\u092a\u0947\u0938\u093f\u091f\u0940 \u0924\u092f \u0928\u0939\u0940\u0902 \u0915\u0930 \u0938\u0915\u0924\u093e\u0964 \u092f\u0947 \u0928\u093f\u0930\u094d\u0923\u092f \u092c\u094b\u0930\u0939\u094b\u0932 \u0921\u0947\u091f\u093e, \u092a\u094d\u0930\u092f\u094b\u0917\u0936\u093e\u0932\u093e \u092a\u0930\u0940\u0915\u094d\u0937\u0923 \u0914\u0930 \u092f\u094b\u0917\u094d\u092f \u091c\u093f\u092f\u094b\u091f\u0947\u0915\u094d\u0928\u093f\u0915\u0932 \u0907\u0902\u091c\u0940\u0928\u093f\u092f\u0930 \u0915\u0940 \u0938\u094d\u0935\u0940\u0915\u0943\u0924\u093f \u092a\u0930 \u0928\u093f\u0930\u094d\u092d\u0930 \u0939\u0948\u0902\u0964 \u092f\u0939 \u092a\u094d\u0932\u0947\u091f\u092b\u0949\u0930\u094d\u092e \u0915\u0947\u0935\u0932 \u092a\u094d\u0930\u093e\u0930\u0902\u092d\u093f\u0915 \u0938\u094d\u0915\u094d\u0930\u0940\u0928\u093f\u0902\u0917 \u0914\u0930 \u091c\u093e\u0902\u091a \u0915\u0940 \u092a\u094d\u0930\u093e\u0925\u092e\u093f\u0915\u0924\u093e \u092c\u0924\u093e\u0924\u093e \u0939\u0948\u0964"),

    (["why", "high risk", "classified", "reason"],
     "A project is rated high risk when several acquisition indicators fail at once. The model "
     "weighs pending compensation most heavily, then active legal disputes, then overdue "
     "statutory approvals, then documentation gaps, possession status, R&R progress and "
     "stakeholder responsiveness. Open the Risk Prediction page and run your numbers: the "
     "Explainable AI panel shows exactly how many percentage points each factor contributed.",
     "\u0915\u094b\u0908 \u092a\u0930\u093f\u092f\u094b\u091c\u0928\u093e \u0909\u091a\u094d\u091a \u091c\u094b\u0916\u093f\u092e \u0935\u093e\u0932\u0940 \u092e\u093e\u0928\u0940 \u091c\u093e\u0924\u0940 \u0939\u0948 \u091c\u092c \u0915\u0908 \u0938\u0902\u0915\u0947\u0924\u0915 \u0938\u093e\u0925 \u092e\u0947\u0902 \u0916\u0930\u093e\u092c \u0939\u094b\u0902 \u2014 \u0932\u0902\u092c\u093f\u0924 \u092e\u0941\u0906\u0935\u091c\u093e, \u0915\u093e\u0928\u0942\u0928\u0940 \u0935\u093f\u0935\u093e\u0926, \u0932\u0902\u092c\u093f\u0924 \u0938\u094d\u0935\u0940\u0915\u0943\u0924\u093f\u092f\u093e\u0902, \u0926\u0938\u094d\u0924\u093e\u0935\u0947\u091c\u0940 \u0915\u092e\u0940 \u0914\u0930 \u0915\u092c\u094d\u091c\u093e \u0915\u0940 \u0938\u094d\u0925\u093f\u0924\u093f\u0964 Risk Prediction \u092a\u0947\u091c \u092a\u0930 Explainable AI \u092a\u0948\u0928\u0932 \u092a\u094d\u0930\u0924\u094d\u092f\u0947\u0915 \u0915\u093e\u0930\u0915 \u0915\u093e \u092f\u094b\u0917\u0926\u093e\u0928 \u0926\u093f\u0916\u093e\u0924\u093e \u0939\u0948\u0964"),

    (["cause", "causes", "delay", "acquisition delay", "major reasons"],
     "The recurring causes of land acquisition delay in Indian infrastructure projects are: "
     "compensation disputes and slow disbursement, litigation over valuation or title, "
     "incomplete or non-digitised land records, overdue statutory and forest clearances, "
     "resistance where rehabilitation entitlements lag, fragmented small holdings that multiply "
     "the number of parties, and weak coordination between the executing agency and revenue "
     "authorities. Compensation and litigation together account for most of the lost time.",
     "\u092d\u0942\u092e\u093f \u0905\u0927\u093f\u0917\u094d\u0930\u0939\u0923 \u092e\u0947\u0902 \u0926\u0947\u0930\u0940 \u0915\u0947 \u092e\u0941\u0916\u094d\u092f \u0915\u093e\u0930\u0923: \u092e\u0941\u0906\u0935\u091c\u093e \u0935\u093f\u0935\u093e\u0926 \u0914\u0930 \u0927\u0940\u092e\u093e \u092d\u0941\u0917\u0924\u093e\u0928, \u092e\u0942\u0932\u094d\u092f\u093e\u0902\u0915\u0928 \u092f\u093e \u0938\u094d\u0935\u093e\u092e\u093f\u0924\u094d\u0935 \u092a\u0930 \u092e\u0941\u0915\u0926\u092e\u0947, \u0905\u092a\u0942\u0930\u094d\u0923 \u092d\u0942-\u0905\u092d\u093f\u0932\u0947\u0916, \u0932\u0902\u092c\u093f\u0924 \u0935\u0928 \u0914\u0930 \u0938\u093e\u0902\u0935\u093f\u0927\u093f\u0915 \u0938\u094d\u0935\u0940\u0915\u0943\u0924\u093f\u092f\u093e\u0902, \u092a\u0941\u0928\u0930\u094d\u0935\u093e\u0938 \u092e\u0947\u0902 \u0935\u093f\u0932\u0902\u092c, \u0914\u0930 \u0935\u093f\u092d\u093e\u0917\u094b\u0902 \u0915\u0947 \u092c\u0940\u091a \u0938\u092e\u0928\u094d\u0935\u092f \u0915\u0940 \u0915\u092e\u0940\u0964"),

    (["uttarakhand", "hill", "mountain", "road in uttarakhand"],
     "Before building a road in Uttarakhand, check these in order: slope angle and slope "
     "stability along the alignment, landslide susceptibility and past failure locations, "
     "cross-drainage and flash-flood behaviour of the nearest stream, seismic zone (much of the "
     "state is Zone IV-V), cut-slope and muck disposal planning, forest and eco-sensitive zone "
     "clearance, working-season length given monsoon and snow, and all-weather access for "
     "materials. The Study Area page loads district-level sample values for exactly this check.",
     "\u0909\u0924\u094d\u0924\u0930\u093e\u0916\u0902\u0921 \u092e\u0947\u0902 \u0938\u0921\u093c\u0915 \u092c\u0928\u093e\u0928\u0947 \u0938\u0947 \u092a\u0939\u0932\u0947 \u0926\u0947\u0916\u0947\u0902: \u0922\u0932\u093e\u0928 \u0915\u093e \u0915\u094b\u0923 \u0914\u0930 \u0938\u094d\u0925\u093f\u0930\u0924\u093e, \u092d\u0942\u0938\u094d\u0916\u0932\u0928 \u0938\u0902\u0935\u0947\u0926\u0928\u0936\u0940\u0932\u0924\u093e, \u091c\u0932 \u0928\u093f\u0915\u093e\u0938\u0940 \u0914\u0930 \u0905\u091a\u093e\u0928\u0915 \u092c\u093e\u0922\u093c, \u092d\u0942\u0915\u0902\u092a \u091c\u094b\u0928 (IV-V), \u0915\u091f\u093e\u0928 \u0914\u0930 \u092e\u0932\u092c\u093e \u0928\u093f\u0938\u094d\u0924\u093e\u0930\u0923, \u0935\u0928 \u0938\u094d\u0935\u0940\u0915\u0943\u0924\u093f, \u0914\u0930 \u092e\u094c\u0938\u092e\u0940 \u0915\u093e\u0930\u094d\u092f \u0905\u0935\u0927\u093f\u0964 Study Area \u092a\u0947\u091c \u092a\u0930 \u091c\u093f\u0932\u093e\u0935\u093e\u0930 \u0928\u092e\u0942\u0928\u093e \u092e\u093e\u0928 \u0926\u0947\u0916\u0947\u0902\u0964"),

    (["landslide", "slope stability", "slope"],
     "High landslide risk in this platform means the combination of slope angle, drainage "
     "condition and recorded past failures puts the location in the upper band of our screening "
     "scale. Practically it means you should expect slope protection works, plan a detailed "
     "geological and slope stability study, avoid toe cutting of unstable slopes, design proper "
     "surface and subsurface drainage, and treat monsoon months as non-working for cut slopes. "
     "It does not mean a landslide is predicted on any particular date.",
     "\u0909\u091a\u094d\u091a \u092d\u0942\u0938\u094d\u0916\u0932\u0928 \u091c\u094b\u0916\u093f\u092e \u0915\u093e \u0905\u0930\u094d\u0925 \u0939\u0948 \u0915\u093f \u0922\u0932\u093e\u0928, \u091c\u0932 \u0928\u093f\u0915\u093e\u0938\u0940 \u0914\u0930 \u092a\u093f\u091b\u0932\u0940 \u0918\u091f\u0928\u093e\u0913\u0902 \u0915\u0947 \u0906\u0927\u093e\u0930 \u092a\u0930 \u092f\u0939 \u0938\u094d\u0925\u093e\u0928 \u0938\u094d\u0915\u094d\u0930\u0940\u0928\u093f\u0902\u0917 \u092e\u0947\u0902 \u0909\u091a\u094d\u091a \u0936\u094d\u0930\u0947\u0923\u0940 \u092e\u0947\u0902 \u0939\u0948\u0964 \u0935\u093f\u0938\u094d\u0924\u0943\u0924 \u0922\u0932\u093e\u0928 \u0938\u094d\u0925\u093f\u0930\u0924\u093e \u0905\u0927\u094d\u092f\u092f\u0928, \u0938\u0941\u0930\u0915\u094d\u0937\u093e \u0915\u093e\u0930\u094d\u092f \u0914\u0930 \u0909\u091a\u093f\u0924 \u091c\u0932 \u0928\u093f\u0915\u093e\u0938\u0940 \u0906\u0935\u0936\u094d\u092f\u0915 \u0939\u0948\u0964 \u092f\u0939 \u0915\u093f\u0938\u0940 \u0924\u093e\u0930\u0940\u0916 \u0915\u0940 \u092d\u0935\u093f\u0937\u094d\u092f\u0935\u093e\u0923\u0940 \u0928\u0939\u0940\u0902 \u0939\u0948\u0964"),

    (["flood", "drainage", "flash flood", "cloudburst"],
     "Flood and flash-flood screening looks at river proximity, drainage capacity and recorded "
     "extreme rainfall exposure. Where it is high, review the highest flood level for the "
     "design return period, size cross-drainage structures for debris-laden flow rather than "
     "clear water, protect embankment toes, and keep construction camps and stockyards out of "
     "the floodplain. In hill catchments, cloudburst-driven flow arrives with very little "
     "warning, so drainage capacity matters more than average rainfall figures.",
     "\u092c\u093e\u0922\u093c \u0914\u0930 \u0905\u091a\u093e\u0928\u0915 \u092c\u093e\u0922\u093c \u0938\u094d\u0915\u094d\u0930\u0940\u0928\u093f\u0902\u0917 \u092e\u0947\u0902 \u0928\u0926\u0940 \u0915\u0940 \u0928\u093f\u0915\u091f\u0924\u093e, \u091c\u0932 \u0928\u093f\u0915\u093e\u0938\u0940 \u0915\u094d\u0937\u092e\u0924\u093e \u0914\u0930 \u0905\u0924\u094d\u092f\u0927\u093f\u0915 \u0935\u0930\u094d\u0937\u093e \u0915\u094b \u0926\u0947\u0916\u093e \u091c\u093e\u0924\u093e \u0939\u0948\u0964 \u0909\u091a\u094d\u091a \u091c\u094b\u0916\u093f\u092e \u092e\u0947\u0902 HFL \u0938\u092e\u0940\u0915\u094d\u0937\u093e, \u092c\u0921\u093c\u0940 \u0915\u094d\u0930\u0949\u0938-\u0921\u094d\u0930\u0947\u0928\u0947\u091c \u0938\u0902\u0930\u091a\u0928\u093e\u090f\u0902 \u0914\u0930 \u092c\u093e\u0922\u093c \u0915\u094d\u0937\u0947\u0924\u094d\u0930 \u0938\u0947 \u0915\u0948\u0902\u092a \u0939\u091f\u093e\u0928\u093e \u0906\u0935\u0936\u094d\u092f\u0915 \u0939\u0948\u0964"),

    (["geotechnical", "soil", "spt", "borehole", "groundwater"],
     "Geotechnical screening here converts early-stage inputs - soil description, SPT N-value, "
     "groundwater depth, depth to rock, moisture, cohesion and friction angle - into indicator "
     "scores for stability, settlement risk, excavation risk and groundwater concern, plus an "
     "investigation priority. Use it to decide where to drill first and how deep to plan the "
     "investigation, not to size a foundation.",
     "\u092f\u0939\u093e\u0902 \u091c\u093f\u092f\u094b\u091f\u0947\u0915\u094d\u0928\u093f\u0915\u0932 \u0938\u094d\u0915\u094d\u0930\u0940\u0928\u093f\u0902\u0917 \u092e\u093f\u091f\u094d\u091f\u0940 \u0915\u093e \u092a\u094d\u0930\u0915\u093e\u0930, SPT \u092e\u093e\u0928, \u092d\u0942\u091c\u0932 \u0938\u094d\u0924\u0930 \u0914\u0930 \u091a\u091f\u094d\u091f\u093e\u0928 \u0915\u0940 \u0917\u0939\u0930\u093e\u0908 \u0938\u0947 \u0938\u094d\u0925\u093f\u0930\u0924\u093e, \u0928\u093f\u092a\u0924\u0928 \u091c\u094b\u0916\u093f\u092e \u0914\u0930 \u091c\u093e\u0902\u091a \u092a\u094d\u0930\u093e\u0925\u092e\u093f\u0915\u0924\u093e \u092c\u0924\u093e\u0924\u0940 \u0939\u0948\u0964 \u092f\u0939 \u0928\u0940\u0902\u0935 \u0921\u093f\u091c\u093e\u0907\u0928 \u0915\u0947 \u0932\u093f\u090f \u0928\u0939\u0940\u0902 \u0939\u0948\u0964"),

    (["compare", "comparison", "site a", "better site", "alternative"],
     "Open Site Comparison and load three candidate districts with the same project type and "
     "size. The platform scores each on terrain, landslide, flood, acquisition, geotechnical "
     "and construction risk, then names the best-scoring option as a preliminary preference. "
     "Treat it as a shortlisting aid: the final choice still needs survey, environmental and "
     "statutory investigation.",
     "Site Comparison \u092a\u0947\u091c \u092a\u0930 \u0924\u0940\u0928 \u0938\u094d\u0925\u093e\u0928\u094b\u0902 \u0915\u0940 \u0924\u0941\u0932\u0928\u093e \u0915\u0930\u0947\u0902\u0964 \u092a\u094d\u0932\u0947\u091f\u092b\u0949\u0930\u094d\u092e \u092d\u0942-\u092d\u093e\u0917, \u092d\u0942\u0938\u094d\u0916\u0932\u0928, \u092c\u093e\u0922\u093c, \u0905\u0927\u093f\u0917\u094d\u0930\u0939\u0923 \u0914\u0930 \u091c\u093f\u092f\u094b\u091f\u0947\u0915\u094d\u0928\u093f\u0915\u0932 \u091c\u094b\u0916\u093f\u092e \u092a\u0930 \u0905\u0902\u0915 \u0926\u0947\u0924\u093e \u0939\u0948 \u0914\u0930 \u092a\u094d\u0930\u093e\u0930\u0902\u092d\u093f\u0915 \u0930\u0942\u092a \u0938\u0947 \u0938\u092c\u0938\u0947 \u0905\u091a\u094d\u091b\u093e \u0935\u093f\u0915\u0932\u094d\u092a \u0938\u0941\u091d\u093e\u0924\u093e \u0939\u0948\u0964"),

    (["data", "dataset", "accuracy", "trained", "synthetic"],
     "The delay model is a Random Forest trained on synthetic sample data generated inside this "
     "prototype, because verified historical acquisition records are not openly available to "
     "us. Its fit statistics describe that synthetic data only and should not be read as "
     "real-world accuracy. For production, the same pipeline would be retrained on verified "
     "departmental records, GSI landslide susceptibility, DEM-derived slope, CWC flood data and "
     "BIS seismic zoning.",
     "\u092f\u0939 \u092e\u0949\u0921\u0932 \u092a\u094d\u0930\u094b\u091f\u094b\u091f\u093e\u0907\u092a \u0915\u0947 \u0905\u0902\u0926\u0930 \u092c\u0928\u093e\u090f \u0917\u090f \u0938\u093f\u0902\u0925\u0947\u091f\u093f\u0915 \u0928\u092e\u0942\u0928\u093e \u0921\u0947\u091f\u093e \u092a\u0930 \u092a\u094d\u0930\u0936\u093f\u0915\u094d\u0937\u093f\u0924 Random Forest \u0939\u0948\u0964 \u0907\u0938\u0915\u0940 \u0938\u091f\u0940\u0915\u0924\u093e \u0935\u093e\u0938\u094d\u0924\u0935\u093f\u0915 \u0926\u0941\u0928\u093f\u092f\u093e \u0915\u0940 \u0938\u091f\u0940\u0915\u0924\u093e \u0928\u0939\u0940\u0902 \u0939\u0948\u0964 \u0909\u0924\u094d\u092a\u093e\u0926\u0928 \u092e\u0947\u0902 \u0938\u0930\u0915\u093e\u0930\u0940 \u0938\u0924\u094d\u092f\u093e\u092a\u093f\u0924 \u0921\u0947\u091f\u093e \u0915\u093e \u0909\u092a\u092f\u094b\u0917 \u0939\u094b\u0917\u093e\u0964"),

    (["before build", "checklist", "what should i check", "pre-construction"],
     "A pre-construction checklist this platform supports: confirm land ownership and "
     "encumbrance status, verify compensation and R&R closure, confirm statutory and forest "
     "clearances, run slope stability screening on the alignment, check flood level and "
     "drainage adequacy, apply the correct seismic zone factor, plan the geotechnical "
     "investigation depth and borehole spacing, and confirm all-weather access and muck "
     "disposal sites. Run Before You Build to get the site-specific version of this.",
     "\u0928\u093f\u0930\u094d\u092e\u093e\u0923 \u0938\u0947 \u092a\u0939\u0932\u0947 \u091c\u093e\u0902\u091a \u0938\u0942\u091a\u0940: \u0938\u094d\u0935\u093e\u092e\u093f\u0924\u094d\u0935 \u0914\u0930 \u092c\u094b\u091d \u0938\u094d\u0925\u093f\u0924\u093f, \u092e\u0941\u0906\u0935\u091c\u093e \u0914\u0930 \u092a\u0941\u0928\u0930\u094d\u0935\u093e\u0938 \u092a\u0942\u0930\u094d\u0923\u0924\u093e, \u0938\u093e\u0902\u0935\u093f\u0927\u093f\u0915 \u0938\u094d\u0935\u0940\u0915\u0943\u0924\u093f\u092f\u093e\u0902, \u0922\u0932\u093e\u0928 \u0938\u094d\u0925\u093f\u0930\u0924\u093e, \u092c\u093e\u0922\u093c \u0938\u094d\u0924\u0930 \u0914\u0930 \u091c\u0932 \u0928\u093f\u0915\u093e\u0938\u0940, \u092d\u0942\u0915\u0902\u092a \u091c\u094b\u0928, \u091c\u093e\u0902\u091a \u0917\u0939\u0930\u093e\u0908 \u0914\u0930 \u092a\u0939\u0941\u0902\u091a \u092e\u093e\u0930\u094d\u0917\u0964"),

    (["r&r", "rehabilitation", "resettlement", "families", "compensation"],
     "Compensation and R&R are the single biggest schedule lever in acquisition. Publish a "
     "beneficiary-wise disbursement tracker, close valuation objections before award where "
     "possible, complete R&R entitlements ahead of taking possession, and keep a dated "
     "grievance redressal calendar. Projects that treat R&R as a follow-on activity are the "
     "ones that stall at possession.",
     "\u092e\u0941\u0906\u0935\u091c\u093e \u0914\u0930 \u092a\u0941\u0928\u0930\u094d\u0935\u093e\u0938 \u0938\u092e\u092f-\u0938\u0940\u092e\u093e \u092a\u0930 \u0938\u092c\u0938\u0947 \u092c\u0921\u093c\u093e \u092a\u094d\u0930\u092d\u093e\u0935 \u0921\u093e\u0932\u0924\u0947 \u0939\u0948\u0902\u0964 \u0932\u093e\u092d\u093e\u0930\u094d\u0925\u0940-\u0935\u093e\u0930 \u091f\u094d\u0930\u0948\u0915\u0930 \u092a\u094d\u0930\u0915\u093e\u0936\u093f\u0924 \u0915\u0930\u0947\u0902, \u0915\u092c\u094d\u091c\u093e \u0932\u0947\u0928\u0947 \u0938\u0947 \u092a\u0939\u0932\u0947 \u092a\u0941\u0928\u0930\u094d\u0935\u093e\u0938 \u092a\u0942\u0930\u093e \u0915\u0930\u0947\u0902 \u0914\u0930 \u0936\u093f\u0915\u093e\u092f\u0924 \u0928\u093f\u0935\u093e\u0930\u0923 \u0915\u0948\u0932\u0947\u0902\u0921\u0930 \u0930\u0916\u0947\u0902\u0964"),

    (["earthquake", "seismic", "zone"],
     "Seismic screening here reports the BIS zone and a vulnerability indicator. Much of the "
     "Himalayan belt sits in Zone IV and V, which affects design forces, detailing, bridge "
     "bearings and retaining structures. The platform flags exposure; the actual design "
     "response spectrum and detailing must come from IS 1893 and a qualified structural engineer.",
     "\u092d\u0942\u0915\u0902\u092a \u0938\u094d\u0915\u094d\u0930\u0940\u0928\u093f\u0902\u0917 BIS \u091c\u094b\u0928 \u0914\u0930 \u0938\u0902\u0935\u0947\u0926\u0928\u0936\u0940\u0932\u0924\u093e \u0938\u0942\u091a\u0915 \u0926\u093f\u0916\u093e\u0924\u0940 \u0939\u0948\u0964 \u0939\u093f\u092e\u093e\u0932\u092f\u0940 \u0915\u094d\u0937\u0947\u0924\u094d\u0930 \u0915\u093e \u092c\u0921\u093c\u093e \u092d\u093e\u0917 \u091c\u094b\u0928 IV-V \u092e\u0947\u0902 \u0939\u0948\u0964 \u0935\u093e\u0938\u094d\u0924\u0935\u093f\u0915 \u0921\u093f\u091c\u093e\u0907\u0928 IS 1893 \u0914\u0930 \u092f\u094b\u0917\u094d\u092f \u0938\u0902\u0930\u091a\u0928\u093e \u0907\u0902\u091c\u0940\u0928\u093f\u092f\u0930 \u0938\u0947 \u0939\u094b\u0928\u093e \u091a\u093e\u0939\u093f\u090f\u0964"),
]

FALLBACK = (
    "I can help with land acquisition delay, terrain and slope, landslide and flood screening, "
    "geotechnical screening, site comparison, Uttarakhand district conditions, and what to check "
    "before construction. Try asking: \"What are the major causes of land acquisition delay?\", "
    "\"What should I check before building a road in Uttarakhand?\", or \"Can AI determine pile depth?\"",
    "\u092e\u0948\u0902 \u092d\u0942\u092e\u093f \u0905\u0927\u093f\u0917\u094d\u0930\u0939\u0923 \u0926\u0947\u0930\u0940, \u092d\u0942-\u092d\u093e\u0917, \u092d\u0942\u0938\u094d\u0916\u0932\u0928 \u0914\u0930 \u092c\u093e\u0922\u093c \u0938\u094d\u0915\u094d\u0930\u0940\u0928\u093f\u0902\u0917, \u091c\u093f\u092f\u094b\u091f\u0947\u0915\u094d\u0928\u093f\u0915\u0932 \u091c\u093e\u0902\u091a \u0914\u0930 \u0938\u094d\u0925\u093e\u0928 \u0924\u0941\u0932\u0928\u093e \u092e\u0947\u0902 \u092e\u0926\u0926 \u0915\u0930 \u0938\u0915\u0924\u093e \u0939\u0942\u0902\u0964 \u0915\u0941\u091b \u092a\u0942\u091b\u0947\u0902: \"\u092d\u0942\u092e\u093f \u0905\u0927\u093f\u0917\u094d\u0930\u0939\u0923 \u092e\u0947\u0902 \u0926\u0947\u0930\u0940 \u0915\u0947 \u0915\u093e\u0930\u0923?\"",
)


def answer_question(question, language="en"):
    """Score the question against the knowledge base and return the best match.

    TO CONNECT A REAL LLM LATER: replace the body of this function with your
    API call, and fall back to this keyword matcher when the call fails or no
    API key is configured. The rest of the app only calls answer_question().
    """
    text = (question or "").lower().strip()
    if not text:
        return {"answer": FALLBACK[0] if language == "en" else FALLBACK[1], "matched": None}

    best_entry, best_score = None, 0
    for keywords, english, hindi in KNOWLEDGE_BASE:
        score = 0
        for keyword in keywords:
            if keyword in text:
                # Longer keyword matches are more specific, so weight them more.
                score += 2 + len(keyword.split())
        if score > best_score:
            best_entry, best_score = (keywords, english, hindi), score

    if best_entry is None:
        return {"answer": FALLBACK[0] if language == "en" else FALLBACK[1], "matched": None}

    keywords, english, hindi = best_entry
    return {
        "answer": english if language == "en" else hindi,
        "matched": keywords[0],
    }
