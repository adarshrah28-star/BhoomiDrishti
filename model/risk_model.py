"""
BhoomiDrishti - Land acquisition delay risk model.

WHAT THIS FILE DOES
-------------------
1. Builds a SYNTHETIC training dataset (because verified historical
   government acquisition data is not publicly available to us).
2. Trains a scikit-learn RandomForestRegressor to predict a
   "delay probability" between 0 and 100.
3. Explains a single prediction by switching one feature at a time to a
   "healthy project" baseline and measuring how much the prediction drops.
   That drop is the feature's contribution for THIS project.

HONESTY NOTE
------------
The model learns the patterns of our synthetic generator, not of real
projects. It must be presented as a prototype only. Accuracy numbers
reported here describe fit on synthetic data and say nothing about
real-world performance.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

# ---------------------------------------------------------------------------
# 1. Feature definitions
# ---------------------------------------------------------------------------

# The order of this list is the order the model expects its inputs in.
FEATURES = [
    "compensation_pending",       # % of compensation still not disbursed
    "legal_disputes",             # count of active disputes
    "pending_approvals",          # count of overdue statutory approvals
    "documentation_completion",   # % of land records complete
    "possession_acquired",        # % of land physically handed over
    "rr_progress",                # % Rehabilitation & Resettlement progress
    "stakeholder_responsiveness", # % responsiveness of stakeholders
    "affected_families",          # number of displaced/affected families
    "land_area",                  # hectares
    "terrain_factor",             # 1 = plain, 2 = foothill, 3 = mountain
]

# Human-readable labels used on the Explainable AI screen.
FEATURE_LABELS = {
    "compensation_pending": "Compensation pending",
    "legal_disputes": "Legal disputes",
    "pending_approvals": "Pending approvals",
    "documentation_completion": "Documentation gaps",
    "possession_acquired": "Possession not taken",
    "rr_progress": "R&R progress shortfall",
    "stakeholder_responsiveness": "Stakeholder responsiveness",
    "affected_families": "Affected families",
    "land_area": "Land area",
    "terrain_factor": "Terrain difficulty",
}

# A "clean" reference project. To explain a prediction we ask:
# "what if only this one field looked healthy?"
BASELINE = {
    "compensation_pending": 5,
    "legal_disputes": 0,
    "pending_approvals": 0,
    "documentation_completion": 98,
    "possession_acquired": 95,
    "rr_progress": 95,
    "stakeholder_responsiveness": 92,
    "affected_families": 60,
    "land_area": 60,
    "terrain_factor": 1,
}


# ---------------------------------------------------------------------------
# 2. Synthetic dataset
# ---------------------------------------------------------------------------

def make_synthetic_dataset(n_rows=4000, seed=42):
    """Create a labelled sample dataset for the prototype.

    We invent each project's characteristics randomly, then compute a delay
    score with a transparent weighted formula and add random noise. The
    Random Forest then has to *learn* that relationship back from the data.
    """
    rng = np.random.default_rng(seed)

    data = pd.DataFrame({
        "compensation_pending": rng.uniform(0, 100, n_rows),
        "legal_disputes": rng.integers(0, 13, n_rows),
        "pending_approvals": rng.integers(0, 9, n_rows),
        "documentation_completion": rng.uniform(30, 100, n_rows),
        "possession_acquired": rng.uniform(10, 100, n_rows),
        "rr_progress": rng.uniform(10, 100, n_rows),
        "stakeholder_responsiveness": rng.uniform(20, 100, n_rows),
        "affected_families": rng.integers(10, 1000, n_rows),
        "land_area": rng.uniform(5, 400, n_rows),
        "terrain_factor": rng.integers(1, 4, n_rows),
    })

    # Weighted "ground truth" for the synthetic world (0-100 scale).
    score = (
        0.26 * data["compensation_pending"]
        + 0.20 * (data["legal_disputes"] / 12 * 100)
        + 0.14 * (data["pending_approvals"] / 8 * 100)
        + 0.10 * (100 - data["documentation_completion"])
        + 0.10 * (100 - data["possession_acquired"])
        + 0.07 * (100 - data["rr_progress"])
        + 0.06 * (100 - data["stakeholder_responsiveness"])
        + 0.03 * (data["affected_families"] / 1000 * 100)
        + 0.02 * (data["land_area"] / 400 * 100)
        + 0.02 * ((data["terrain_factor"] - 1) / 2 * 100)
    )

    noise = rng.normal(0, 4.5, n_rows)
    data["delay_probability"] = np.clip(score + noise, 2, 98)
    return data


# ---------------------------------------------------------------------------
# 3. The model wrapper
# ---------------------------------------------------------------------------

class DelayRiskModel:
    """Trains once when the Flask app starts, then answers predictions."""

    def __init__(self):
        self.model = None
        self.metrics = {}
        self.global_importance = []

    def train(self):
        df = make_synthetic_dataset()
        x = df[FEATURES]
        y = df["delay_probability"]

        x_train, x_test, y_train, y_test = train_test_split(
            x, y, test_size=0.2, random_state=42
        )

        self.model = RandomForestRegressor(
            n_estimators=200, max_depth=14, min_samples_leaf=3, random_state=42
        )
        self.model.fit(x_train, y_train)

        predicted = self.model.predict(x_test)
        self.metrics = {
            "rows_trained": int(len(x_train)),
            "mae": round(float(mean_absolute_error(y_test, predicted)), 2),
            "r2": round(float(r2_score(y_test, predicted)), 3),
            "data_source": "Synthetic / sample data generated inside this prototype",
        }

        # Global feature importance, sorted high to low.
        pairs = sorted(
            zip(FEATURES, self.model.feature_importances_),
            key=lambda item: item[1],
            reverse=True,
        )
        self.global_importance = [
            {"feature": name, "label": FEATURE_LABELS[name],
             "percent": round(float(value) * 100, 1)}
            for name, value in pairs
        ]
        return self.metrics

    # -- prediction --------------------------------------------------------

    def _row(self, values):
        """Turn a dict of inputs into the 1-row frame the model expects."""
        clean = {}
        for name in FEATURES:
            clean[name] = float(values.get(name, BASELINE[name]))
        return pd.DataFrame([clean])[FEATURES]

    def predict(self, values):
        probability = float(self.model.predict(self._row(values))[0])
        return round(max(0.0, min(100.0, probability)), 1)

    def explain(self, values, top_n=6):
        """Local explanation by baseline substitution.

        For each feature we re-run the prediction with only that feature
        replaced by its healthy baseline. The size of the drop tells us how
        much that feature is pushing this project's risk up.
        """
        base_prediction = self.predict(values)
        drops = []

        for name in FEATURES:
            what_if = dict(values)
            what_if[name] = BASELINE[name]
            drops.append((name, max(0.0, base_prediction - self.predict(what_if))))

        total = sum(drop for _, drop in drops)
        if total <= 0:
            return []

        drops.sort(key=lambda item: item[1], reverse=True)
        factors = []
        for name, drop in drops[:top_n]:
            if drop <= 0:
                continue
            factors.append({
                "feature": name,
                "label": FEATURE_LABELS[name],
                "percent": round(drop / total * 100, 1),
                "impact_points": round(drop, 1),
            })
        return factors


# ---------------------------------------------------------------------------
# 4. Helpers shared by the whole app
# ---------------------------------------------------------------------------

def risk_category(probability):
    """Convert a 0-100 delay probability into a four-level band."""
    if probability >= 75:
        return "CRITICAL"
    if probability >= 55:
        return "HIGH"
    if probability >= 35:
        return "MEDIUM"
    return "LOW"


def expected_delay_range(probability):
    """Illustrative delay window tied to the probability band."""
    if probability >= 85:
        return "8-14 months"
    if probability >= 75:
        return "6-10 months"
    if probability >= 55:
        return "4-7 months"
    if probability >= 35:
        return "2-4 months"
    return "0-2 months"


def terrain_factor_for(terrain_text):
    """Map a terrain description to the 1-3 factor the model uses."""
    text = (terrain_text or "").lower()
    if "mountain" in text or "high" in text:
        return 3
    if "hill" in text or "foothill" in text or "valley" in text or "plateau" in text:
        return 2
    return 1


if __name__ == "__main__":
    # Lets you sanity-check the model on its own:  python model/risk_model.py
    m = DelayRiskModel()
    print("Training metrics (synthetic data only):", m.train())
    sample = {
        "compensation_pending": 78, "legal_disputes": 9, "pending_approvals": 6,
        "documentation_completion": 54, "possession_acquired": 31, "rr_progress": 38,
        "stakeholder_responsiveness": 42, "affected_families": 412,
        "land_area": 148.5, "terrain_factor": 3,
    }
    p = m.predict(sample)
    print("Delay probability:", p, risk_category(p), expected_delay_range(p))
    for f in m.explain(sample):
        print(" ", f["label"], f["percent"], "%")
