# BhoomiDrishti

**Know the Land Before You Build.**

AI-powered land acquisition, site suitability and pre-construction risk intelligence platform.
Smart India Hackathon 2026 prototype.

> Prototype built on synthetic and sample data. AI-generated preliminary screening only. Final
> foundation design, pile depth, bearing capacity and structural decisions require site-specific
> geotechnical investigation and qualified engineering approval. This is not a certified
> engineering system and is not integrated with any government platform.

---

## 1. Running it on Windows

### Step 1 — Install Python

Download Python 3.11 or 3.12 from <https://www.python.org/downloads/>.
On the first installer screen, **tick "Add python.exe to PATH"** before clicking Install.
Check it worked by opening Command Prompt and running:

```
python --version
```

### Step 2 — Install VS Code

Download from <https://code.visualstudio.com/>. Install the **Python** extension by Microsoft
(Extensions sidebar, search "Python").

### Step 3 — Open the project folder

In VS Code: `File` → `Open Folder…` → select the `BhoomiDrishti` folder (the one containing
`app.py`).

### Step 4 — Open the terminal

`Terminal` → `New Terminal`. Make sure the prompt ends in `\BhoomiDrishti>`.

### Step 5 — Create a virtual environment

```
python -m venv venv
venv\Scripts\activate
```

The prompt should now start with `(venv)`.

If PowerShell blocks the activate script, run this once and then retry:

```
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### Step 6 — Install the requirements

```
pip install -r requirements.txt
```

### Step 7 — Run the app

```
python app.py
```

You will see the model train on startup:

```
BhoomiDrishti: training prototype risk model on synthetic data...
BhoomiDrishti: model ready -> {'rows_trained': 3200, ...}
 * Running on http://127.0.0.1:5000
```

### Step 8 — Open it in a browser

<http://127.0.0.1:5000>

Sign in with any demo account:

| Username | Password | Role |
|---|---|---|
| admin | admin123 | Administrator |
| officer | officer123 | Government Officer |
| contractor | contractor123 | Contractor |
| manager | manager123 | Project Manager |

Stop the server with `Ctrl + C`.

---

## 2. Demo flow for the SIH presentation

1. **Dashboard** — portfolio KPIs, risk distribution, state and district risk, top delay drivers, critical projects table.
2. **Risk Prediction** — the form is pre-filled with a severe mountain highway. Click **Predict delay risk**.
3. Point at the three result cards: delay probability, risk category, expected delay range.
4. **Explainable AI** — show which factors produced that number and read the generated sentence.
5. Scroll to **Recommended actions** — each one names the trigger that fired it.
6. Click **Load a healthy project**, predict again, and show the score collapsing. This proves the model is responding to inputs, not printing a constant.
7. **Before You Build** — select Chamoli, project type Road, click **Assess this site**. Show the suitability dial, the risk radar and the hazard bars.
8. **Study Area** — click through Uttarakhand districts; show the state-wide comparison chart.
9. **Site Comparison** — compare Chamoli, Nainital and Dehradun. The recommended site appears automatically with the caveat line.
10. **GIS Risk Map** — filter to Critical, click **Zoom to Uttarakhand**, open a marker popup.
11. **Geotechnical Screening** — run it, then point at the investigation depth and priority, and read the disclaimer aloud. This is the honesty moment of the demo.
12. **Alerts** — filter to Critical only.
13. **BhoomiAI** — ask "Can AI determine pile depth?" It refuses correctly and explains what the platform does instead. Then switch the top-bar language to हिन्दी and ask again.

---

## 3. What each module does

| Page | What it produces |
|---|---|
| Dashboard | Portfolio KPIs, six charts, critical projects table with filter |
| Risk Prediction | Delay probability, risk category, expected delay, explainable AI, actions |
| Project Monitoring | All sample projects with search and filters, per-project detail panel |
| Before You Build | Site suitability score plus eight risk dimensions and recommendations |
| Study Area | District-level Uttarakhand terrain and hazard profiles |
| Land History | Record summary, acquisition timeline, dispute and documentation status |
| Proposed Plan | Land requirement from geometry, acquisition complexity, alternatives |
| Terrain Analysis | Elevation, slope, construction difficulty, slope stability, implications |
| Disaster Risk | Six hazard gauges, composite exposure, mitigation actions |
| Geotechnical Screening | Stability, settlement, excavation, groundwater indicators, investigation depth |
| Contractor View | Site-team view of one project: critical issues and actions |
| Site Comparison | Three sites scored on identical criteria, best option named |
| GIS Risk Map | Leaflet map with risk-coloured markers and popups |
| AI Recommendations | Per-project and portfolio-wide action lists |
| Alerts | Severity-filtered alert cards |
| BhoomiAI | Offline rule-based assistant, English and Hindi |
| Data Intelligence | Documented data sources with Connected / Prototype / Future status |
| Resources | Reference categories with placeholders for official sources |
| About | Model details, limits, architecture |

---

## 4. How the model works

`model/risk_model.py`:

1. Generates 4,000 synthetic projects with random acquisition indicators.
2. Labels each one using a transparent weighted formula plus random noise.
3. Trains a `RandomForestRegressor` to learn that relationship back.
4. Predicts a delay probability from 0 to 100, which maps to LOW / MEDIUM / HIGH / CRITICAL.

**Explainability.** For each input field, the prediction is re-run with only that field reset to
a "healthy project" baseline. The drop in predicted risk is that field's contribution *for this
specific project*, normalised to a percentage. This is ablation attribution: simpler than SHAP,
no extra dependency, and local rather than global, so two projects with the same score can have
completely different explanations.

**On accuracy.** The reported mean absolute error and R-squared describe how well the model
recovered its own synthetic generator. They are not a claim about real projects and should never
be presented as accuracy. A production build would retrain the same pipeline on verified
departmental acquisition records.

`model/rules.py` holds the rule engine: terrain analysis, disaster screening, geotechnical
screening, site assessment, the recommendation rules and the BhoomiAI knowledge base. It is
deliberately rule-based so every number on screen traces back to an explicit formula.

---

## 5. Project structure

```
BhoomiDrishti/
├── app.py                  Flask routes and JSON APIs
├── requirements.txt
├── README.md
├── smoke_test.py           Checks every route and API still works
├── data/
│   ├── projects.csv        15 sample projects
│   └── districts.json      19 district terrain and hazard profiles
├── model/
│   ├── __init__.py
│   ├── risk_model.py       Synthetic data, Random Forest, explanations
│   └── rules.py            Rule engine, recommendations, chatbot
├── templates/              19 Jinja templates, all extending base.html
└── static/
    ├── css/style.css
    └── js/app.js           Shared helpers, chart defaults, language toggle
```

Verify everything works at any time:

```
python smoke_test.py
```

---

## 6. Common errors and fixes

**`'python' is not recognized`**
Python is not on PATH. Reinstall it with "Add python.exe to PATH" ticked, or use `py` instead of
`python`.

**`venv\Scripts\activate : cannot be loaded because running scripts is disabled`**
PowerShell execution policy. Run
`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`, answer `Y`, then retry.

**`ModuleNotFoundError: No module named 'flask'`**
The virtual environment is not active (no `(venv)` in the prompt) or the install step was
skipped. Run `venv\Scripts\activate` then `pip install -r requirements.txt`.

**`ModuleNotFoundError: No module named 'model'`**
You are running from the wrong folder. `cd` into the folder that contains `app.py` and run
`python app.py` from there.

**`Address already in use` / `Port 5000 is in use`**
An old server is still running. Close the other terminal, or change the last line of `app.py` to
`port=5001` and use <http://127.0.0.1:5001>.

**Charts or the map are blank**
Chart.js and Leaflet load from a CDN, so those need an internet connection. Everything else runs
offline. If you must demo without internet, download `chart.umd.min.js`, `leaflet.js` and
`leaflet.css` into `static/js/` and `static/css/`, then point the `<script>` and `<link>` tags in
`templates/base.html` and `templates/map.html` at the local copies.

**`pip install` fails on scikit-learn or numpy**
Usually a Python version mismatch. Use Python 3.11 or 3.12. If it still fails, install without
pinned versions: `pip install flask pandas numpy scikit-learn`.

**Page loads but a section stays empty**
Open the browser console with `F12` and read the error, then check the Flask terminal. The
terminal shows the Python traceback for any failing API call.

---

## 7. What to build next

In rough order of value for a judging panel:

1. **Replace the synthetic dataset.** Everything else is scaffolding around this. Even 200 real historical projects with known delay outcomes would change the model from a demonstration into a tool.
2. **Add SQLite persistence.** Right now `projects.csv` is read once at startup and nothing is saved. Add a `projects`, `assessments`, `alerts` and `users` schema so assessments can be re-opened and compared over time.
3. **Use a real elevation model.** District-average slope is the weakest input in the platform. Sampling SRTM or Bhuvan elevation along an actual alignment would make terrain and landslide scores site-specific instead of district-wide.
4. **Draw the alignment on the map.** Let a user trace a proposed corridor with Leaflet Draw and score every 500 m segment, so the output is a risk profile along a route rather than one number for a district.
5. **Swap the chatbot for a real model.** `answer_question()` in `model/rules.py` is a single function; replace its body with an API call and keep the keyword matcher as the offline fallback.
6. **Proper authentication and true role-based access.** The prototype checks a hardcoded dictionary and every role can open every page. Hash passwords and gate routes by role.
