"""
SmartBuy — Data Sources Registry
==================================
The official challenge requires every external source to be documented:
  - Origin
  - Date / frequency
  - Expected reliability
  - How it influences the recommendation

This file is the single source of truth for all data sources used.
It is also exposed via the API so the dashboard can show source documentation.
"""

SOURCES = {

    # ─── PROVIDED BY DAMM ────────────────────────────────────────────────────

    "damm_barley": {
        "name": "Damm Barley Dataset",
        "origin": "Damm internal — provided at hackathon",
        "type": "internal",
        "frequency": "Daily (6 months of history)",
        "reliability": "HIGH — primary source, direct from Damm procurement",
        "format": "CSV",
        "path": "data/barley_damm.csv",          # <-- place Damm's file here
        "influence": "Direct price input for barley buy score and trend model",
        "notes": "Confidential — only used within hackathon context",
    },

    "cala_structured": {
        "name": "Cala.ai Structured Price Data",
        "origin": "Cala.ai — hackathon partner",
        "type": "partner_api",
        "frequency": "On demand",
        "reliability": "HIGH — verified, structured, hallucination-free",
        "format": "JSON via API",
        "influence": (
            "Primary structured price feed for all materials. "
            "Replaces or supplements synthetic data when available."
        ),
        "notes": (
            "Cala extracts, verifies and structures data from internet sources "
            "including ICIS, Fastmarkets, Expana. Use as the trusted data layer "
            "feeding into feature engineering."
        ),
    },

    # ─── FREE PUBLIC SOURCES ──────────────────────────────────────────────────

    "fred_barley": {
        "name": "IMF Global Barley Price (FRED)",
        "origin": "International Monetary Fund via Federal Reserve Bank of St. Louis",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PBARLUSDM",
        "type": "public_api",
        "frequency": "Monthly",
        "reliability": "HIGH — IMF benchmark, representative of global market",
        "format": "CSV — direct URL fetch, no API key needed",
        "influence": "Barley baseline price and 24-month trend for historical analogues",
        "notes": "Prices in USD/metric tonne. Updated ~6 weeks after month end.",
    },

    "fred_aluminium": {
        "name": "IMF Global Aluminium Price (FRED)",
        "origin": "IMF via Federal Reserve Bank of St. Louis",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PALUMUSDM",
        "type": "public_api",
        "frequency": "Monthly",
        "reliability": "HIGH — LME reference price",
        "format": "CSV — direct URL fetch",
        "influence": "Aluminium baseline price, trend model, historical analogues",
        "notes": "USD/metric tonne. Aluminium is Damm's highest-spend category.",
    },

    "fred_oil_brent": {
        "name": "Brent Crude Oil Price (FRED)",
        "origin": "IMF via Federal Reserve Bank of St. Louis",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=POILBREUSDM",
        "type": "public_api",
        "frequency": "Monthly",
        "reliability": "HIGH",
        "format": "CSV — direct URL fetch",
        "influence": (
            "Upstream driver for PET (PTA+MEG are oil derivatives). "
            "Also affects aluminium smelting energy costs and logistics."
        ),
    },

    "fred_natural_gas_eu": {
        "name": "EU Natural Gas Price (FRED/World Bank)",
        "origin": "World Bank via FRED",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PNGASEUUSDM",
        "type": "public_api",
        "frequency": "Monthly",
        "reliability": "HIGH",
        "format": "CSV",
        "influence": (
            "Key driver for aluminium (energy-intensive smelting) and glass. "
            "Also affects CO2 production costs."
        ),
    },

    "fred_wheat": {
        "name": "IMF Global Wheat Price (FRED)",
        "origin": "IMF via FRED",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PWHEAMTUSDM",
        "type": "public_api",
        "frequency": "Monthly",
        "reliability": "HIGH",
        "format": "CSV",
        "influence": (
            "Proxy for barley price direction — wheat and barley are substitutes "
            "in animal feed and brewing. Correlation ~0.85."
        ),
    },

    "fred_sugar": {
        "name": "IMF Global Sugar Price (FRED)",
        "origin": "IMF via FRED",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PSUGAISAUSDM",
        "type": "public_api",
        "frequency": "Monthly",
        "reliability": "HIGH",
        "format": "CSV",
        "influence": "Direct input for sugar buy score (Damm Lemon and soft drink lines)",
    },

    "fred_eurusd": {
        "name": "EUR/USD Exchange Rate (FRED)",
        "origin": "Federal Reserve via FRED",
        "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXUSEU",
        "type": "public_api",
        "frequency": "Daily",
        "reliability": "HIGH",
        "format": "CSV",
        "influence": (
            "All commodity prices are in USD. EUR/USD converts them to EUR "
            "for Damm's actual cost base."
        ),
    },

    "google_news_rss": {
        "name": "Google News RSS Feeds",
        "origin": "Google News — aggregated from Reuters, Bloomberg, ICIS, FT etc.",
        "url": "https://news.google.com/rss/search?q={query}&hl=en",
        "type": "public_rss",
        "frequency": "Real-time",
        "reliability": "MEDIUM — aggregated, varies by source",
        "format": "RSS/XML — parsed with feedparser",
        "influence": (
            "News sentiment input. Headlines classified by FinBERT (HuggingFace) "
            "for fast scoring and Claude for driver explanation."
        ),
        "queries_used": [
            "aluminium price supply",
            "PET plastic price Europe",
            "barley malt supply crop",
            "Brent crude oil OPEC",
            "Turkey petrochemical export",
            "EU energy price industrial",
            "Baltic Dry Index shipping",
            "LME aluminium futures",
        ],
    },

    "cot_reports": {
        "name": "CFTC Commitments of Traders (COT) Report",
        "origin": "US Commodity Futures Trading Commission",
        "url": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
        "type": "public_report",
        "frequency": "Weekly (released every Friday)",
        "reliability": "HIGH — regulatory filing, legally required",
        "format": "CSV download",
        "influence": (
            "Speculative positioning in commodity futures. "
            "Large net-long positions by funds = price likely to rise. "
            "Used as an advanced signal, as mentioned in challenge brief."
        ),
        "notes": (
            "Available for corn/wheat (barley proxy) and energy futures. "
            "Aluminium COT via LME weekly bulletin."
        ),
    },

    "eurostat_imports": {
        "name": "Eurostat COMEXT Trade Data",
        "origin": "European Commission — Eurostat",
        "url": "https://ec.europa.eu/eurostat/web/international-trade-in-goods/data/database",
        "type": "public_api",
        "frequency": "Monthly (2-month lag)",
        "reliability": "HIGH — official EU statistics",
        "format": "CSV/API",
        "influence": (
            "EU PET import volumes from Turkey and Asia. "
            "Rising imports → supply pressure → bearish for PET price."
        ),
    },

    "huggingface_finbert": {
        "name": "FinBERT Sentiment Model (HuggingFace)",
        "origin": "ProsusAI/finbert on HuggingFace Hub",
        "url": "https://huggingface.co/ProsusAI/finbert",
        "type": "ml_model_api",
        "frequency": "On demand — per headline",
        "reliability": "MEDIUM-HIGH — trained on financial news corpus",
        "format": "HuggingFace Inference API",
        "influence": (
            "First-pass sentiment classification of news headlines. "
            "Returns positive/negative/neutral + confidence score. "
            "Used to filter and prioritise headlines before Claude analysis."
        ),
        "cost": "Uses HuggingFace credits — ~$0.0001 per headline",
    },

    "synthetic_fallback": {
        "name": "Synthetic Data Generator",
        "origin": "SmartBuy internal — data_ingestion.py",
        "type": "synthetic",
        "frequency": "Generated on first run",
        "reliability": "LOW — for demo only",
        "format": "Pandas DataFrame",
        "influence": "Fallback when live APIs are unavailable",
        "notes": "Replace with real data before production use.",
    },
}


def get_sources_for_material(material_id: str) -> list[dict]:
    """Returns the list of sources relevant to a given material."""
    MATERIAL_SOURCES = {
        "aluminium": [
            "damm_barley", "fred_aluminium", "fred_natural_gas_eu",
            "fred_eurusd", "cot_reports", "google_news_rss", "huggingface_finbert",
        ],
        "vpet": [
            "fred_oil_brent", "fred_eurusd", "eurostat_imports",
            "cala_structured", "google_news_rss", "huggingface_finbert",
        ],
        "rpet": [
            "fred_oil_brent", "eurostat_imports", "cala_structured",
            "google_news_rss", "huggingface_finbert",
        ],
        "barley": [
            "damm_barley", "fred_barley", "fred_wheat", "fred_eurusd",
            "cot_reports", "google_news_rss", "huggingface_finbert",
        ],
        "energy": [
            "fred_natural_gas_eu", "fred_oil_brent", "fred_eurusd",
            "cot_reports", "google_news_rss",
        ],
        "sugar": [
            "fred_sugar", "fred_eurusd", "google_news_rss",
        ],
    }
    source_ids = MATERIAL_SOURCES.get(material_id, [])
    return [{"id": sid, **SOURCES[sid]} for sid in source_ids if sid in SOURCES]


def get_all_sources() -> dict:
    return SOURCES
