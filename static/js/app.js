/* ==========================================================================
   BhoomiDrishti - shared frontend helpers
   Loaded on every page by base.html. Page-specific code lives at the bottom
   of each template inside a <script> block.
   ========================================================================== */

/* ---------- Colours matching the CSS risk bands ---------- */
const RISK_COLORS = {
  LOW: "#3fbf8f",
  MEDIUM: "#e0a83c",
  HIGH: "#f1735c",
  CRITICAL: "#e4485d",
};
const TEAL = "#35d0ba";
const BLUE = "#4c9aff";
const GRID = "#1f3b47";
const TEXT_DIM = "#9fb6bf";

/* Convert any 0-100 risk number into a band label. */
function band(value) {
  if (value >= 75) return "CRITICAL";
  if (value >= 55) return "HIGH";
  if (value >= 35) return "MEDIUM";
  return "LOW";
}

function riskColor(value) {
  return RISK_COLORS[band(value)];
}

/* ---------- Small DOM helpers ---------- */
function $(selector) { return document.querySelector(selector); }
function $$(selector) { return Array.from(document.querySelectorAll(selector)); }

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

/* A labelled progress row: name, value, coloured bar. */
function metricRow(name, value, suffix = "") {
  const level = band(value);
  return `
    <div class="metric-row">
      <div class="metric-name">${escapeHtml(name)}</div>
      <div class="metric-value">${value}${suffix}</div>
      <div><div class="bar-track"><div class="bar-fill ${level}" style="width:${Math.min(100, value)}%"></div></div></div>
    </div>`;
}

function badge(level) {
  return `<span class="badge ${level}">${level}</span>`;
}

/* Render a recommendation list into a container element. */
function renderRecommendations(container, items) {
  if (!container) return;
  if (!items || !items.length) {
    container.innerHTML = '<p class="muted">No recommendations generated.</p>';
    return;
  }
  container.innerHTML = items.map(function (item, index) {
    return `
      <div class="reco ${item.priority}">
        <div class="reco-index">${index + 1}</div>
        <div>
          <div class="reco-action">${escapeHtml(item.action)}</div>
          <div class="reco-meta">${badge(item.priority)} &nbsp;Triggered by: ${escapeHtml(item.trigger)}${item.why ? " &middot; " + escapeHtml(item.why) : ""}</div>
        </div>
      </div>`;
  }).join("");
}

/* ---------- Talking to the Flask API ---------- */
async function postJSON(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Request failed: " + response.status);
  return response.json();
}

async function getJSON(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error("Request failed: " + response.status);
  return response.json();
}

/* Read a whole form into a plain object. */
function formValues(formElement) {
  const values = {};
  new FormData(formElement).forEach(function (value, key) { values[key] = value; });
  return values;
}

/* ---------- Chart.js shared defaults ---------- */
function applyChartDefaults() {
  if (typeof Chart === "undefined") return;
  Chart.defaults.color = TEXT_DIM;
  Chart.defaults.font.family = '"Segoe UI", Roboto, Arial, sans-serif';
  Chart.defaults.font.size = 11.5;
  Chart.defaults.borderColor = GRID;
  Chart.defaults.plugins.legend.labels.boxWidth = 11;
  Chart.defaults.plugins.legend.labels.boxHeight = 11;
  Chart.defaults.maintainAspectRatio = false;
}

/* Axis config reused by bar and line charts. */
function axes(maxValue) {
  return {
    x: { grid: { color: GRID, drawBorder: false }, ticks: { autoSkip: false, maxRotation: 45 } },
    y: { beginAtZero: true, max: maxValue, grid: { color: GRID, drawBorder: false } },
  };
}

/* A doughnut used as a score dial. Pass a canvas id. */
function scoreDial(canvasId, score, color) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return null;
  if (canvas._chart) canvas._chart.destroy();
  canvas._chart = new Chart(canvas, {
    type: "doughnut",
    data: {
      datasets: [{
        data: [score, 100 - score],
        backgroundColor: [color, "#1a3540"],
        borderWidth: 0,
        cutout: "76%",
      }],
    },
    options: {
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      animation: { duration: 400 },
    },
  });
  return canvas._chart;
}

/* Replace an existing chart on a canvas, so re-running a form works. */
function drawChart(canvasId, config) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return null;
  if (canvas._chart) canvas._chart.destroy();
  canvas._chart = new Chart(canvas, config);
  return canvas._chart;
}

/* ---------- Language toggle (English / Hindi) ---------- */
/* Add data-i18n="key" to any element you want translated. */
const TRANSLATIONS = {
  "nav.dashboard": ["Dashboard", "डैशबोर्ड"],
  "nav.prediction": ["Risk Prediction", "जोखिम पूर्वानुमान"],
  "nav.projects": ["Project Monitoring", "परियोजना निगरानी"],
  "nav.before_build": ["Before You Build", "निर्माण से पहले"],
  "nav.study_area": ["Study Area", "अध्ययन क्षेत्र"],
  "nav.land_history": ["Land History", "भूमि इतिहास"],
  "nav.planning": ["Proposed Plan", "प्रस्तावित योजना"],
  "nav.terrain": ["Terrain Analysis", "भू-भाग विश्लेषण"],
  "nav.disaster": ["Disaster Risk", "आपदा जोखिम"],
  "nav.geotechnical": ["Geotechnical Screening", "जियोटेक्निकल जांच"],
  "nav.contractor": ["Contractor View", "ठेकेदार दृश्य"],
  "nav.comparison": ["Site Comparison", "स्थल तुलना"],
  "nav.map": ["GIS Risk Map", "जीआईएस जोखिम मानचित्र"],
  "nav.recommendations": ["AI Recommendations", "एआई सिफारिशें"],
  "nav.alerts": ["Alerts", "चेतावनियां"],
  "nav.assistant": ["BhoomiAI Assistant", "भूमिAI सहायक"],
  "nav.data_intelligence": ["Data Intelligence", "डेटा इंटेलिजेंस"],
  "nav.resources": ["Resources", "संसाधन"],
  "nav.about": ["About", "परिचय"],
  "nav.logout": ["Sign out", "साइन आउट"],

  "group.overview": ["Overview", "अवलोकन"],
  "group.assess": ["Assess a site", "स्थल मूल्यांकन"],
  "group.act": ["Act on findings", "कार्रवाई"],
  "group.reference": ["Reference", "संदर्भ"],

  "label.risk": ["Risk level", "जोखिम स्तर"],
  "label.delay": ["Delay probability", "देरी की संभावना"],
  "label.suitability": ["Site suitability", "स्थल उपयुक्तता"],
  "label.predict": ["Predict delay risk", "देरी जोखिम का अनुमान"],
  "label.assess": ["Assess this site", "इस स्थल का मूल्यांकन"],
  "label.compare": ["Compare sites", "स्थलों की तुलना"],
  "label.screen": ["Run screening", "जांच चलाएं"],
};

function currentLanguage() {
  return localStorage.getItem("bd-lang") || "en";
}

function applyLanguage(lang) {
  const index = lang === "hi" ? 1 : 0;
  $$("[data-i18n]").forEach(function (element) {
    const pair = TRANSLATIONS[element.getAttribute("data-i18n")];
    if (pair) element.textContent = pair[index];
  });
  $$(".lang-toggle button").forEach(function (button) {
    button.classList.toggle("active", button.dataset.lang === lang);
  });
  document.documentElement.lang = lang;
  localStorage.setItem("bd-lang", lang);
}

document.addEventListener("DOMContentLoaded", function () {
  applyChartDefaults();
  applyLanguage(currentLanguage());

  $$(".lang-toggle button").forEach(function (button) {
    button.addEventListener("click", function () { applyLanguage(button.dataset.lang); });
  });

  /* Range sliders show their live value next to the handle. */
  $$("input[type=range]").forEach(function (slider) {
    const output = document.getElementById(slider.id + "-value");
    if (!output) return;
    const sync = function () { output.textContent = slider.value + (slider.dataset.suffix || ""); };
    slider.addEventListener("input", sync);
    sync();
  });
});
