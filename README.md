# SmartBuy — AI Decision Support System for Raw Materials

> **E-Hub × Damm Hackathon 2026**
> 
> *Should we buy now, wait, hedge, or monitor?*

---

## What we do

SmartBuy is a Decision Support System that transforms raw commodity price data, energy signals, satellite indicators, and real-time news into a single actionable procurement recommendation per raw material — with full explainability at every step.

It is not a price forecasting tool. It is a **procurement timing engine** built specifically for a company that buys, not trades.

### Four possible recommendations

| Action | Meaning | When triggered |
|--------|---------|----------------|
| **BUY** | Order now at current price | Price below average + supply risk rising + trend up |
| **WAIT** | Delay purchase | Price falling + supply comfortable + no urgency |
| **HEDGE** | Lock in current price via forward contract | Supply risk HIGH but price uncertain |
| **MONITOR** | No action needed | Stable conditions — reassess in 5–7 days |

---

## Materials Covered

| Material | Model | Key Signal |
|----------|-------|------------|
| **Aluminium** | 5-layer specialist model | China 45Mt cap utilisation |
| **Barley** | 5-layer specialist model | NDVI + Protein Paradox |
| **vPET** | Generic 4-component model | Oil price correlation |
| **rPET** | Generic 4-component model | EU 30% mandate compliance |
| **Energy (TTF)** | Generic 4-component model | Strait of Hormuz / LNG disruption |

---

## Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env
# Edit .env with your keys (see DOCUMENTATION.md)

# 3. Seed price history (run once)
python3 backend/price_history.py seed

# 4. Fetch real news
python3 backend/fetch_real_news.py

# 5. Start the backend
python3 backend/server.py

# 6. Start the frontend (new terminal)
cd frontend && npm install && npm run dev
```

Open **http://localhost:3000**

---

## Strategic Decision Drivers

### Aluminium: Supply Rigidity & Energy
* **China’s 45Mt Cap**: Tracks the legal production ceiling in China. As utilization nears 96%, supply becomes inelastic, making prices hyper-sensitive to demand shocks.
* **Energy Input Delta**: Monitors the spread between EU Electricity prices (smelter viability) and China Coal (global cost floor) to determine regional supply shifts.
* **Yunnan Hydropower Proxy**: Real-time rainfall monitoring in China's smelting hubs to anticipate power-related supply curtailments before they hit the LME.

### Barley: Quality & Climate Yield
* **The Protein/Quality Gap**: Predicts the availability of Malting-grade vs. Feed-grade barley. High-temperature forecasts during June are flagged as a risk to grain quality, even if total harvest volume remains high.
* **Fertilizer Link**: Correlates Natural Gas (TTF) fluctuations with future harvest yields via nitrogen fertilizer affordability and farmer planting intentions.

### FinBERT News Scoring
* Real headlines fetched daily from Google News RSS, classified using HuggingFace's ProsusAI/finbert model. Procurement signal derived from aggregate sentiment, not individual headlines.

---

## Data Sources

| Source | Material | Type |
|--------|----------|------|
| Yahoo Finance (ALI=F) | Aluminium | Live |
| OMIP / TradingEconomics | Energy / TTF | Reference |
| ICIS Europe | vPET, rPET | Reference |
| Expana / Black Sea | Barley | Reference |
| LME Warrant Report | Aluminium | Weekly |
| MIIT / China NBS | Aluminium | Monthly |
| JRC MARS / Copernicus | Barley | Monthly |
| FRED (IMF/World Bank) | All (history) | Monthly |
| Google News RSS + FinBERT | All | Daily |
| Cala.ai | All | On demand |

---

## Team - 67Birras
* **Guillem Arévalo Morell** 
* **Mikel Carbonés Núñez**
* **Emma Leroux Fernández-Armesto**

Built at the E-Hub × Damm Hackathon, May 2026.
