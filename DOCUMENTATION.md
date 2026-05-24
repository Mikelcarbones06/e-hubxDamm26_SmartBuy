# SmartBuy — Full Technical Documentation

> **E-Hub × Damm Hackathon 2026**
> May 2026

---

## Table of Contents

1. [Project Overview & Business Problem](#1-project-overview--business-problem)
2. [Core Drivers & Variables](#2-core-drivers--variables)
3. [Recommendation Engine & Scoring Logic](#3-recommendation-engine--scoring-logic)
4. [Challenge Alignment Checklist](#4-challenge-alignment-checklist)
5. [Technical Stack & Repository Structure](#5-technical-stack--repository-structure)
6. [User Flow & Demo Instructions](#6-user-flow--demo-instructions)
7. [Configuration & API Keys](#7-configuration--api-keys)
8. [Limitations & Roadmap](#8-limitations--roadmap)

---

## 1. Project Overview & Business Problem

### The Problem

Damm's procurement team manages five critical raw materials — aluminium (beer cans), vPET and rPET (bottles), malted barley (brewing), and natural gas (energy) — across dozens of suppliers and three continents. Each purchasing decision involves:

- **Price risk**: commodity prices can swing 15–20% in weeks
- **Supply risk**: geopolitical events, weather, and government policy can restrict availability regardless of price
- **Quality risk** (specific to barley): a record harvest year can simultaneously produce a shortage of malting-grade grain if heat waves push protein content above 12%
- **Lead time pressure**: aluminium has a 28-day lead time, meaning the decision must be made before the price moves

Existing tools give the team a price chart. SmartBuy gives them a decision.

### The Solution

SmartBuy is an AI-driven Decision Support System that:

1. Aggregates commodity prices, energy costs, satellite data, geopolitical signals, and classified news into a single **SmartBuy Score (0–100)** per material
2. Translates that score into one of four **actionable recommendations**: BUY, WAIT, HEDGE, or MONITOR
3. Explains every recommendation with sourced evidence — drivers pushing price up, drivers pushing price down, and all signals that fed into the score
4. Compares current conditions to similar historical episodes with quantified outcomes
5. Provides a procurement-aware AI chatbot that answers questions in the context of real current data

### Why This Is Not a Trading Tool

SmartBuy is explicitly designed for a **buyer**, not a trader. This distinction changes every part of the model:

- **BUY** means "order now before the price rises further" — not "go long"
- **WAIT** means "delay purchase to save money as prices fall" — not "go short"
- **HEDGE** means "lock in current price via forward contract" — not "open a derivative position"
- Budget impact is calculated in EUR/month at Damm's actual consumption volumes
- Lead times (28 days for aluminium, 10 days for barley) are built into the urgency logic

---

## 2. Core Drivers & Variables

### A. Aluminium — Supply-Shock & Energy Model

Aluminium is Damm's highest-spend raw material and the one with the most complex supply structure. The model uses five layers, each representing a distinct causal mechanism.

#### Layer 1 — LME Price & Warehouse Stocks (max 20 pts)

The London Metal Exchange (LME) weekly warrant report publishes the volume of aluminium held in certified warehouses globally. This is the single most reliable short-term signal for physical market tightness.

- **Below 700kt**: critically low — price reacts violently to any supply news
- **700–1,200kt**: normal range — balanced market
- **Above 1,400kt**: ample supply — price under pressure

*Source: LME.com weekly warrant report. Reference value: 780kt (May 2026)*

#### Layer 2 — Energy Input Costs (max 20 pts)

Electricity represents 30–40% of aluminium smelting cost. The model monitors two energy benchmarks simultaneously:

**EU Electricity (TTF proxy):**
- Below €40/MWh: smelters profitable, production stable → bearish
- €40–€80/MWh: elevated but manageable
- Above €80/MWh: smelters lose money → production cuts → supply falls → price rises (this was the 2021 Energy Crisis mechanism)

**China Coal (Newcastle thermal):**
- Drives 55% of global aluminium production
- Above $130/t: Chinese smelter margins squeezed → output cuts
- Below $80/t: Chinese smelters very profitable → risk of flooding the market

*Sources: OMIP / TradingEconomics (EU electricity). Yahoo Finance QL=F (coal).*

#### Layer 3 — China's 45Mt Production Cap (max 25 pts)

This is the most structurally important signal in the model. In 2020, Beijing's Ministry of Industry and Information Technology (MIIT) imposed a hard ceiling of 45 million tonnes per year on primary aluminium production. As of May 2026, China is producing approximately 43Mt — operating at **95.6% of the legal ceiling**.

The critical insight: **when China is near the cap, supply cannot grow even if prices rise**. Normally, high aluminium prices incentivise producers to expand output. At 95.6% of cap, this mechanism is broken. Any demand increase hits prices directly.

A secondary signal — the Coal/Cap Paradox — occurs when coal is cheap (producers want to produce more) but the cap prevents them. This is an unusually powerful buy signal because economics and policy point in opposite directions, and policy wins.

*Source: MIIT 2025–2027 Aluminium Industry Action Plan. Verified by Cala.ai.*

**Scoring:**
- ≥98% utilisation: 24 pts — CRITICAL, supply cannot grow
- ≥95% utilisation: 19 pts — near cap, structural constraint
- ≥90% utilisation: 13 pts — tightening
- <80% utilisation: 4 pts — spare capacity, bearish

#### Layer 4 — Yunnan Hydropower Proxy (max 25 pts)

Yunnan province in southern China is the primary smelting hub, powered largely by hydroelectricity. This makes it highly vulnerable to rainfall variability. When rainfall falls, cheap power disappears, and smelters cut output — typically 3–4 weeks before the price impact appears in LME data.

This makes Yunnan hydro the model's **leading indicator** — the equivalent of monitoring a drought early warning system, not waiting for the LME to react.

**Thresholds (based on historical episodes):**
- YoY change ≤ -30%: RED ALERT — government will cut smelter power to prioritise domestic consumption. Buy immediately. (2023 El Niño: -1.1Mt curtailed, +15.3% price in 5 months)
- YoY change ≤ -15%: Significant deficit — smelter cuts likely within weeks
- YoY change ≤ -10%: Below normal — monitor closely
- YoY change > +5%: Abundant power — Chinese smelters fully operational, bearish

*Source: China NBS hydropower statistics. Reference value: -8% YoY (May 2026, estimated).*

#### Layer 5 — FinBERT News Sentiment (max 10 pts)

65 real headlines are fetched daily from Google News RSS using commodity-specific search queries. Each headline is classified by HuggingFace's ProsusAI/finbert model — a BERT variant trained specifically on financial text. The model returns a positive/negative/neutral label with a confidence score.

The aggregate score across all aluminium-related headlines feeds into Layer 5. This captures geopolitical events (Middle East disruptions, tariff announcements, Red Sea logistics), regional premium movements, and supply chain news that the structural layers above cannot detect in real time.

*Source: Google News RSS + HuggingFace Inference API (ProsusAI/finbert).*

---

### B. Barley — Quality & Yield Model

Barley procurement for Damm is fundamentally different from aluminium. The key risk is not availability — it is **quality**. Damm requires malting-grade barley, which must meet specific protein content thresholds (below 12%) to be suitable for brewing. This creates the Protein Paradox.

#### Layer 1 — Cost Floor: TTF Gas + Fertiliser (max 20 pts)

EU natural gas directly drives urea and nitrogen fertiliser prices (20–30% of a barley farmer's production cost). When the gas price is high, fertiliser is expensive, farming margins are squeezed, and farmers plant less in subsequent seasons.

More immediately, if the market barley price falls below the farmer's break-even cost (estimated at €185/t for EU production), farmers withhold stock rather than sell at a loss. This **stock retention** creates a price floor — the market cannot fall below production cost sustainably.

*Sources: OMIP / TTF (gas). Agri-benchmark / Expana (break-even estimate).*

#### Layer 2 — Physical Supply: Global Stock-to-Use Ratio (max 20 pts)

The stock-to-use ratio measures global barley inventory as a percentage of annual consumption. When stocks are low, the market reacts violently to any supply news — a drought in one region or a major tender can move prices 5–10% in days.

As of May 2026, the IGC (International Grains Council) forecasts a 4% tightening in global grain inventories for 2026/27, with barley stock-to-use around 18.5%.

**Thresholds:**
- Below 15%: critically tight — price extremely volatile
- 15–18%: tight — elevated risk
- 18–25%: normal range
- Above 25%: comfortable — bearish

*Source: USDA WASDE April 2026. IGC Grains Market Report May 2026.*

#### Layer 3 — NDVI + Heat Wave: The Protein Paradox (max 30 pts — highest weight)

This is SmartBuy's most sophisticated signal for barley, and the one most specific to Damm's needs as a brewer.

**The Protein Paradox** (source: Frontiers in Plant Science, 2022): drought stress during grain fill significantly increases crude protein content in barley. Malting barley must have protein content below 12% (Federal Variety Office standard) to be suitable for brewing. When heat or drought during June (the critical grain fill period) pushes protein above 12%, the grain can only be sold as animal feed — even if total harvest volume is high.

The result: a year with a **record harvest can simultaneously produce a malting-grade shortage**. Damm pays a premium for malting quality, and that premium can surge 20–40% in a protein paradox year even when generic barley prices are flat.

**NDVI (Normalised Difference Vegetation Index)** — satellite measurement of crop health. The model monitors two key regions:
- **Castilla y León (Spain)**: Damm's local sourcing region. Reference NDVI: 0.62 (slightly below normal for May 2026)
- **Northern France**: Europe's primary malting barley production zone. Reference NDVI: 0.68 (below normal, with France's crop rated 71% good/excellent vs 75% normal)

**Heat wave risk during grain fill (June)** is sourced from ECMWF extended range seasonal forecasts. A HIGH or CRITICAL rating triggers the Protein Paradox flag in the model.

*Sources: JRC MARS crop monitoring. Copernicus Land Service. ECMWF seasonal forecast. Frontiers in Plant Science (2022) — peer reviewed.*

#### Layer 4 — Geopolitical / Major Tenders (max 20 pts)

Two demand signals dominate global barley markets:

**Saudi Arabia** — the world's largest barley importer (6–8Mt per year). When Saudi Arabia launches a major tender, it creates demand suction that lifts global prices 3–8% within weeks.

**China** — importing barley at +27% YoY growth as of January–February 2026 (China customs data). China uses barley primarily for animal feed and, increasingly, for craft brewing. Sustained growth at this rate tightens the global supply balance.

**Black Sea export risk** — Ukraine and Russia together export approximately 30% of global barley. Any disruption (conflict escalation, port closures, sanctions) redirects Middle Eastern buyers to EU sources, lifting European prices.

*Sources: USDA FAS. China customs (Jan–Feb 2026). IGC cereals market situation March 2026.*

#### Layer 5 — FinBERT News Sentiment (max 10 pts)

Same methodology as aluminium. Keywords that most strongly predict barley price movements in the training data: "stress", "yield cut", "export ban", "drought", "protein concern", "USDA cuts", "tender".

---

### Three Barley Scenarios

The barley model explicitly maps current conditions to one of three pre-defined scenarios:

**Scenario A — Perfect Storm** 🔴
- Conditions: TTF gas > €50/MWh + France NDVI < 0.65 + Black Sea risk MEDIUM or HIGH
- Action: BUY SEMESTER VOLUME — lock in 6-month forward contracts
- Historical parallel: Summer 2021 (Black Sea tensions + EU drought) → +12.1% in 30 days

**Scenario B — Volume Trap** 🟡
- Conditions: Good harvest volume forecast BUT heat wave risk HIGH during June grain fill
- Action: BUY MALTING GRADE NOW — even though generic barley price looks comfortable
- Historical parallel: Summer 2018 (UK/France heat wave) → malting premium surged 20–40% despite adequate total volume
- This is Damm-specific: a generic barley buyer might WAIT, but Damm needs malting quality specifically

**Scenario C — Bear Market** 🟢
- Conditions: TTF < €35/MWh + NDVI Spain and France both > 0.70 + Global stocks > 22% S/U
- Action: WAIT — spot purchases only, no forward contracts needed
- Historical parallel: Q3 2023 (good EU harvest + cheap gas) → prices fell 5.2%

---

## 3. Recommendation Engine & Scoring Logic

### The SmartBuy Score Formula

```
Score = Σ(Layer_i score)     where max total = 100

Aluminium:
  Layer 1: LME Stocks         0–20 pts
  Layer 2: Energy Costs        0–20 pts
  Layer 3: China Cap           0–25 pts
  Layer 4: Yunnan Hydro        0–25 pts
  Layer 5: News Sentiment      0–10 pts

Barley:
  Layer 1: Cost Floor          0–20 pts
  Layer 2: Physical Supply     0–20 pts
  Layer 3: NDVI + Heat         0–30 pts  ← highest weight
  Layer 4: Geopolitical        0–20 pts
  Layer 5: News Sentiment      0–10 pts

Other materials (vPET, rPET, Energy):
  Price Entry (z-score)        0–35 pts
  Price Trend (regression)     0–25 pts
  Supply Risk (news composite) 0–25 pts
  News Signal (FinBERT)        0–15 pts
```

### Decision Matrix

| Score | Supply Risk | Action |
|-------|-------------|--------|
| ≥ 68 | Any | **BUY** |
| ≥ 55 | HIGH | **BUY** |
| ≥ 45 | Any | **HEDGE** |
| Any | HIGH | **HEDGE** (minimum) |
| ≤ 32 | LOW | **WAIT** |
| All other | — | **MONITOR** |

**Supply risk override**: If supply risk is assessed as HIGH (Yunnan YoY ≤ -15%, or China ≥ 98% cap, or LME stocks < 600kt), the action is at minimum HEDGE regardless of score. Supply continuity takes priority over cost optimisation for a manufacturer.

### Budget Impact Calculation

Every recommendation includes a EUR estimate of the cost of waiting vs acting now:

```
Budget impact = Monthly volume (t) × Current price (EUR/t) × Forecast 30d change (%)

Aluminium: 1,440 t/month
Barley:    6,600 t/month
```

### Historical Analogues (Aluminium only)

For aluminium, the model computes Euclidean distance between the current 5-dimensional driver vector and four curated historical episodes:

```
Distance = √[ Σ(current_driver_i − historical_driver_i)² ]

Similarity % = 1 − (Distance / max_distance)
```

The three episodes — China Supply-Side Reform (2017), European Energy Crisis (2021), Yunnan El Niño (2023) — were curated based on documented market outcomes with real price data. The ghost chart overlay shows the historical price trajectory from the entry point, enabling the procurement team to visualise what happened next in similar conditions.

---

## 4. Challenge Alignment Checklist

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Recommendation system: BUY / WAIT / HEDGE / MONITOR | `models.py`, `aluminium_model.py`, `barley_model.py` | ✅ |
| Risk / opportunity score by raw material (0–100) | 5-layer weighted scoring engine | ✅ |
| Driver explanation: what is pushing prices up or down | `drivers_up` / `drivers_down` lists per recommendation, shown in Evidence panel | ✅ |
| Comparison with similar historical episodes | `aluminium_analogues.py` — Euclidean distance matching, ghost chart, comparison table | ✅ Aluminium |
| Dashboard: select material, see recommendation, evidence, horizon | React dashboard — 5 tabs, material selector, full evidence panel | ✅ |
| Code repository and real working demo | FastAPI backend + React frontend, all dependencies in `requirements.txt` | ✅ |
| Actionability | Horizon stated in plain English ("Order within 14 days"), budget impact in EUR | ✅ |
| Data diversity | Yahoo Finance + OMIP + ICIS + Expana + Cala.ai + JRC MARS + FRED + FinBERT | ✅ |
| Explainability | Evidence & Explainability panel: all signals with ✓/⚠ icons, driver breakdown, score components | ✅ |

---

## 5. Technical Stack & Repository Structure

### Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend | Python 3.9+ / FastAPI | REST API, data processing, model scoring |
| ML / NLP | HuggingFace ProsusAI/finbert | News sentiment classification |
| LLM | Llama3.2 (Ollama, local) / OpenRouter / Gemini | Procurement chatbot and AI briefings |
| Frontend | React 18 / Vite / Recharts | Dashboard and visualisations |
| Data | Yahoo Finance (yfinance) / FRED / Google News RSS | Live and historical prices |
| Scheduling | Python threading + macOS cron | 30-min price refresh, 2-hour news refresh |

### Repository Structure

```
smartbuy_v3/
│
├── .env                          ← API keys (never commit)
├── .env.example                  ← Template
├── requirements.txt              ← Python dependencies
├── README.md                     ← Project overview
├── DOCUMENTATION.md              ← This file
│
├── backend/
│   ├── server.py                 ← FastAPI server, all endpoints, startup
│   ├── aluminium_model.py        ← 5-layer aluminium scoring model
│   ├── barley_model.py           ← 5-layer barley scoring model
│   ├── aluminium_analogues.py    ← Historical episode matching (Euclidean distance)
│   ├── models.py                 ← Generic 4-component model (vPET, rPET, energy)
│   ├── features.py               ← Price feature engineering (MA, Bollinger, z-score)
│   ├── finbert_classifier.py     ← HuggingFace FinBERT classifier
│   ├── news_classifier.py        ← Google News RSS fetcher
│   ├── news_by_material.py       ← Per-material news aggregation and interpretation
│   ├── fetch_real_news.py        ← Standalone news fetch script
│   ├── live_prices.py            ← Yahoo Finance + verified reference prices
│   ├── price_history.py          ← Rolling CSV database, FRED seeding
│   ├── explainer.py              ← LLM integration (Ollama / OpenRouter / Gemini / Claude)
│   ├── openrouter_client.py      ← OpenRouter API client
│   ├── data_ingestion.py         ← Material definitions, synthetic fallback
│   ├── scheduler.py              ← Background refresh threads + cron installer
│   ├── env_loader.py             ← .env file loader
│   └── sources.py                ← Documented data sources
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   ├── public/
│   │   └── damm_logo.png
│   └── src/
│       ├── main.jsx
│       └── SmartBuy.jsx          ← Full React dashboard (615 lines)
│
└── data/                         ← Created automatically on first run
    ├── live_prices.json          ← Today's prices
    ├── news.json                 ← Classified headlines
    ├── aluminium_drivers.json    ← Saved aluminium driver values
    ├── barley_drivers.json       ← Saved barley driver values
    └── history/
        ├── aluminium.csv
        ├── barley.csv
        ├── energy.csv
        ├── vpet.csv
        └── rpet.csv
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard` | All materials summary — polled every 60s |
| GET | `/api/material/{id}` | Full data for one material |
| GET | `/api/prices/{id}` | Historical chart data |
| GET | `/api/news` | All classified headlines |
| GET | `/api/news/material/{id}` | Per-material news with FinBERT aggregate |
| GET | `/api/news/all` | All materials news analysis |
| GET | `/api/narrative/{id}` | AI market briefing |
| GET | `/api/aluminium/drivers` | 5-layer driver values |
| GET | `/api/aluminium/analogues` | Historical episode matching |
| GET | `/api/barley/drivers` | Barley 5-layer driver values |
| GET | `/api/sources` | Documented data sources |
| POST | `/api/chat` | Procurement chatbot |
| POST | `/api/scenario` | What-if scenario analysis |
| POST | `/api/refresh` | Manual data refresh |

### Fallback Mechanisms

The system is designed to always produce a recommendation, even when data sources are unavailable:

1. **Yahoo Finance unavailable** → uses verified reference prices (OMIP, ICIS, Expana)
2. **FRED historical data unavailable** → uses synthetic price series anchored to real current prices
3. **HuggingFace FinBERT unavailable** → falls back to keyword-based sentiment scoring
4. **LLM unavailable** → chatbot returns a clear message with setup instructions; recommendations still work
5. **No news file** → model runs with neutral news sentiment (Layer 5 = 5/10 pts)
6. **No driver file** → models use hardcoded default values with documented sources

---

## 6. User Flow & Demo Instructions

### Step-by-Step User Flow

**Step 1 — Select a material**
Click any of the five material cards at the top. Each shows the action (BUY / WAIT / HEDGE / MONITOR), the SmartBuy Score, and the current price.

**Step 2 — Read the score and action**
The circular gauge shows the score. The coloured badge shows the action. Below it: confidence level, supply risk, and the recommended horizon in plain English.

**Step 3 — Understand the drivers**
For aluminium: the 5-layer panel shows China utilisation, Yunnan hydro, LME stocks, and electricity cost as coloured gauges with real-time thresholds.
For barley: the scenario panel shows whether conditions match Scenario A (Perfect Storm), B (Volume Trap/Protein Paradox), or C (Bear Market).

**Step 4 — Review the evidence**
The Evidence & Explainability panel lists every signal that fed into the score — drivers pushing price up (green), drivers pushing price down (blue), and all evidence signals with ✓/⚠ icons.

**Step 5 — Check historical analogues (aluminium)**
The Historical Analogues panel shows the three most similar past market episodes, ranked by Euclidean distance similarity. The ghost chart overlays the historical price trajectory on today's entry point.

**Step 6 — Review news**
The News tab shows per-material FinBERT analysis: aggregate sentiment score, sentiment bar, procurement signal, and all classified headlines sorted by magnitude.

**Step 7 — Ask the chatbot**
The Chat tab has a procurement-aware AI assistant. Suggested questions include: "Should we buy aluminium now?", "What if Yunnan has a -30% drought?", "Compare aluminium vs barley urgency."

**Step 8 — Generate AI briefing**
In the Overview tab, click "Generate AI Briefing" to produce a structured 3-paragraph market briefing in the format: bold action headline → current situation → 30-day outlook → specific recommendation.

### Installation — macOS

```bash
# Prerequisites: Python 3.9+, Node.js 18+, npm

# 1. Clone or unzip the repository
cd ~/Desktop && unzip smartbuy_v3.zip && cd smartbuy_v3

# 2. Install Python dependencies
pip3 install -r requirements.txt

# 3. Configure API keys
cp .env.example .env
# Edit .env — minimum required: one LLM key

# 4. Download Ollama for local LLM (free, no API key)
brew install ollama
ollama pull llama3.2        # ~2GB download
brew services start ollama  # runs in background

# 5. Seed 3 years of price history from FRED
python3 backend/price_history.py seed

# 6. Fetch today's prices
python3 backend/live_prices.py

# 7. Fetch and classify real news
python3 backend/fetch_real_news.py

# 8. Install automatic daily refresh (run once)
python3 backend/scheduler.py install

# 9. Start the application
# Terminal 1:
python3 backend/server.py

# Terminal 2:
cd frontend && npm install && npm run dev
```

Open **http://localhost:3000**

### Daily Operation (after initial setup)

```bash
# Start backend
cd ~/Desktop/smartbuy_v3
python3 backend/server.py

# Start frontend (new terminal)
cd ~/Desktop/smartbuy_v3/frontend
npm run dev
```

The cron job installed in Step 8 automatically refreshes prices at 7:00am and news every 6 hours — so data is always current when you open the app.

---

## 7. Configuration & API Keys

Create a `.env` file in the `smartbuy_v3/` root directory:

```bash
# LLM for chatbot and AI briefings — add at least one
OPENROUTER_API_KEY=sk-or-...    # Free at openrouter.ai
ANTHROPIC_API_KEY=sk-ant-...    # console.anthropic.com (~$0.01/call)
GEMINI_API_KEY=AIza...          # aistudio.google.com (free tier)

# News sentiment classification
HF_TOKEN=hf_...                 # huggingface.co/settings/tokens (free)
```

The system tries LLMs in order: Claude → OpenRouter → Gemini → Ollama (local). Everything except the chatbot/briefing works without any API key.

---

## 8. Limitations & Roadmap

### Current Limitations

**Reference values for some indicators**
NDVI (Spain 0.62, France 0.68), Yunnan hydro YoY (-8%), and LME warehouse stocks (780kt) are reference estimates, not live feeds. In production, these would connect to:
- Copernicus Land Service API (NDVI, free)
- China NBS monthly statistics (Yunnan hydro)
- LME.com weekly warrant report (warehouse stocks)
- EU ETS carbon price via ICE Futures API

**Price history is partially synthetic**
The 36-month price history for aluminium, barley, and energy is mathematically generated, anchored to real current prices and real historical trends (aluminium rose from $2,200 to $3,600+; barley fell from €270 to €220). In production, this would be replaced by real FRED/LME/ICIS historical data.

**Chatbot speed**
Running Llama3.2 locally on CPU takes 10–30 seconds per response. This is a hardware limitation — in production the system would use Claude or GPT-4 via API for instant responses.

**Historical analogues are curated**
The four aluminium episodes and their driver vectors were set by human research, not calculated from a historical database. The similarity percentages and rankings are mathematically computed, but the episode definitions are manually curated.

### Roadmap

**Short term (next sprint)**
- Live LME stocks via LME.com weekly warrant report scraper
- Real Yunnan hydro data from China NBS monthly statistics API
- EU ETS carbon price integration (ICE Futures free data)
- CFTC Commitments of Traders (COT) report for speculative positioning signal

**Medium term**
- Copernicus Land Service NDVI API integration (free, official EU satellite data)
- ECMWF seasonal forecast API for heat wave risk quantification
- USDA WASDE monthly report parsing via FinBERT for barley supply signals
- Saudi GFSA tender RSS feed monitoring

**Long term**
- Expand historical analogue database from 4 to 50+ episodes using real LME price history
- Build barley historical analogue engine matching the aluminium model
- Add vPET/rPET specialist model with PTA/MEG feedstock tracking
- Multi-user support with role-based access (buyer vs management views)
- Integration with Damm's ERP for inventory-aware recommendations (stock levels affect urgency)

---

## Team - 67Birras
* **Guillem Arévalo Morell** 
* **Mikel Carbonés Núñez**
* **Emma Leroux Fernández-Armesto**

---

*SmartBuy — E-Hub × Damm Hackathon 2026*
*Built with FastAPI, React, HuggingFace FinBERT, and Llama3.2*
