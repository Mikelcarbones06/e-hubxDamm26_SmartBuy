"""
SmartBuy — Data Ingestion
==========================
Priority order for each material:
  1. Damm's provided CSV (if placed in data/ folder)
  2. Cala.ai structured API (if credentials provided)
  3. FRED free public API (real data, no key needed)
  4. Synthetic fallback (demo only)

HOW TO ADD REAL DATA:
  - Place Damm's barley CSV at: data/barley_damm.csv
  - Columns expected: date, price (EUR/tonne or USD/tonne)
  - Everything else loads automatically from FRED
"""

import json
import time
import datetime
import random
from pathlib import Path

import numpy as np
import pandas as pd
import urllib.request


# ─── FRED SERIES IDS ──────────────────────────────────────────────────────────
# All free, no API key needed. Just fetch the URL.

FRED_SERIES = {
    "barley":    "PBARLUSDM",     # IMF Global Barley Price USD/tonne — monthly
    "wheat":     "PWHEAMTUSDM",   # IMF Wheat — proxy for barley direction
    "aluminium": "PALUMUSDM",     # IMF Aluminium USD/tonne — monthly
    "oil":       "POILBREUSDM",   # Brent Crude USD/barrel — monthly
    "nat_gas":   "PNGASEUUSDM",   # EU Natural Gas USD/mmbtu — monthly
    "sugar":     "PSUGAISAUSDM",  # IMF Sugar USD/tonne — monthly
    "eurusd":    "DEXUSEU",       # EUR/USD daily exchange rate
}

# ─── MATERIAL CONFIG ──────────────────────────────────────────────────────────
# The 4 materials explicitly called out in the official brief.
# Plus energy (natural gas) as it drives aluminium costs.

MATERIALS = {
    "aluminium": {
        "name": "Aluminium",
        "unit": "USD/tonne",
        "fred_series": "PALUMUSDM",
        "description": "Highest-spend category at Damm. LME aluminium for can sheet.",
        "key_drivers": ["nat_gas", "oil", "eurusd", "lme_futures"],
        "supplier_origin": "EU mills (Novelis, Constellium)",
        "lead_time_days": 28,
        # REPLACE with real Damm consumption: tonnes per month
        "monthly_consumption_tonnes": 1440,   # ~48t/day × 30 days
        "safety_stock_days": 21,
    },
    "vpet": {
        "name": "Virgin PET (vPET)",
        "unit": "EUR/tonne",
        "fred_series": None,                  # No FRED series — use oil as proxy
        "description": "PET bottles. Price = f(PTA + MEG + fee). Oil-linked.",
        "key_drivers": ["oil", "pta", "meg", "turkey_imports"],
        "supplier_origin": "Turkey / Asia",
        "lead_time_days": 21,
        "monthly_consumption_tonnes": 1740,
        "safety_stock_days": 14,
    },
    "rpet": {
        "name": "Recycled PET (rPET)",
        "unit": "EUR/tonne",
        "fred_series": None,
        "description": "EU mandate: 25% recycled content now, 30% from 2026.",
        "key_drivers": ["eu_regulation", "vpet_price", "recycling_capacity"],
        "supplier_origin": "EU recyclers",
        "lead_time_days": 14,
        "monthly_consumption_tonnes": 540,
        "safety_stock_days": 14,
    },
    "barley": {
        "name": "Malted Barley",
        "unit": "EUR/tonne",
        "fred_series": "PBARLUSDM",
        "description": "Core brewing ingredient. Damm dataset provided for 6 months.",
        "key_drivers": ["wheat_price", "eu_harvest", "spain_drought", "cot_positions"],
        "supplier_origin": "Spain / France",
        "lead_time_days": 10,
        "monthly_consumption_tonnes": 6600,   # ~220t/day
        "safety_stock_days": 14,
    },
    "energy": {
        "name": "Energy (Natural Gas)",
        "unit": "EUR/MWh",
        "fred_series": "PNGASEUUSDM",
        "description": "EU TTF natural gas. Drives aluminium smelting and production costs.",
        "key_drivers": ["geopolitics", "storage_levels", "weather", "renewables"],
        "supplier_origin": "EU grid / spot market (OMIP/TTF)",
        "lead_time_days": 1,
        "monthly_consumption_tonnes": None,    # Metered, not stocked
        "safety_stock_days": 0,
    },
}


# ─── FRED FETCHER ─────────────────────────────────────────────────────────────

def fetch_fred_series(series_id: str, n_years: int = 3) -> pd.DataFrame | None:
    """
    Fetches a FRED time series as a DataFrame.
    Returns None if the fetch fails (no internet, blocked, etc.)

    HOW IT WORKS: FRED publishes every series as a public CSV at a fixed URL.
    No API key, no account, completely free.
    """
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SmartBuy/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            lines = r.read().decode("utf-8").strip().split("\n")

        rows = []
        for line in lines[1:]:           # Skip header
            parts = line.split(",")
            if len(parts) == 2 and parts[1].strip() not in (".", ""):
                rows.append({
                    "date": parts[0].strip(),
                    "value": float(parts[1].strip()),
                })

        if not rows:
            return None

        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        # Keep last n_years of data
        cutoff = pd.Timestamp.now() - pd.DateOffset(years=n_years)
        df = df[df["date"] >= cutoff].reset_index(drop=True)

        return df

    except Exception as e:
        print(f"  [FRED] Could not fetch {series_id}: {e}")
        return None


def fetch_all_fred() -> dict[str, pd.DataFrame]:
    """Fetches all FRED series needed for the models. Returns dict of DataFrames."""
    print("Fetching live data from FRED...")
    result = {}
    for name, series_id in FRED_SERIES.items():
        df = fetch_fred_series(series_id)
        if df is not None:
            result[name] = df
            latest = df.iloc[-1]
            print(f"  ✅ {name:<12} {series_id:<16} latest: {latest['value']:.2f} ({latest['date'].date()})")
        else:
            print(f"  ⚠️  {name:<12} {series_id:<16} — using synthetic fallback")
    return result


# ─── DAMM CSV LOADER ──────────────────────────────────────────────────────────

def load_damm_barley(path: str = "data/barley_damm.csv") -> pd.DataFrame | None:
    """
    Loads Damm's provided barley dataset.
    Expected columns: date, price
    Optional columns: volume, quality_grade, supplier

    HOW TO USE:
      1. Place Damm's CSV at data/barley_damm.csv
      2. Make sure it has at least 'date' and 'price' columns
      3. This function normalises column names automatically

    Returns None if file doesn't exist.
    """
    p = Path(path)
    if not p.exists():
        print(f"  [Damm] Barley CSV not found at {path} — will use FRED/synthetic")
        return None

    try:
        df = pd.read_csv(p)
        df.columns = df.columns.str.lower().str.strip()

        # Flexible column detection
        date_col  = next((c for c in df.columns if "date" in c or "fecha" in c), None)
        price_col = next((c for c in df.columns if "price" in c or "precio" in c or "value" in c), None)

        if not date_col or not price_col:
            print(f"  [Damm] Could not detect date/price columns. Found: {list(df.columns)}")
            return None

        df = df.rename(columns={date_col: "date", price_col: "value"})
        df["date"] = pd.to_datetime(df["date"])
        df = df[["date", "value"]].dropna().sort_values("date").reset_index(drop=True)
        print(f"  ✅ Damm barley CSV loaded: {len(df)} rows, latest: {df.iloc[-1]['value']:.2f} ({df.iloc[-1]['date'].date()})")
        return df

    except Exception as e:
        print(f"  [Damm] Error loading barley CSV: {e}")
        return None


# ─── SYNTHETIC DATA GENERATOR ─────────────────────────────────────────────────

def _make_dates_monthly(n_months: int) -> list[pd.Timestamp]:
    """Generates monthly dates going back n_months from today."""
    today = pd.Timestamp.now()
    return [today - pd.DateOffset(months=i) for i in reversed(range(n_months))]


def generate_synthetic_series(
    n_months: int = 36,
    start: float = 100.0,
    drift: float = 0.002,
    vol: float = 0.04,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generates a realistic price series using geometric Brownian motion.
    Used as fallback when live data is unavailable.

    drift: monthly drift (0.002 = slight uptrend)
    vol:   monthly volatility (0.04 = 4%)
    """
    rng = np.random.default_rng(seed)
    dates = _make_dates_monthly(n_months)
    prices = [start]
    for _ in range(n_months - 1):
        ret = drift + vol * rng.normal()
        prices.append(prices[-1] * (1 + ret))

    return pd.DataFrame({"date": dates, "value": [round(p, 2) for p in prices]})


SYNTHETIC_PARAMS = {
    # material: (start_price, drift, vol, seed)
    # Prices chosen to match realistic 2024 levels
    "barley":    (230.0,  0.001, 0.045, 1),   # USD/tonne — barley ~$200-280
    "wheat":     (220.0,  0.001, 0.050, 2),   # USD/tonne
    "aluminium": (2300.0, 0.003, 0.035, 3),   # USD/tonne — LME ~$2200-2500
    "oil":       (82.0,  -0.002, 0.060, 4),   # USD/barrel — Brent ~$75-90
    "nat_gas":   (12.0,  -0.010, 0.120, 5),   # EU TTF — volatile
    "sugar":     (440.0,  0.002, 0.040, 6),   # USD/tonne
    "eurusd":    (1.085,  0.000, 0.008, 7),   # EUR/USD
    "vpet":      (830.0,  0.003, 0.025, 8),   # EUR/tonne — ~$800-900
    "rpet":      (950.0,  0.004, 0.030, 9),   # EUR/tonne — premium over vPET
}


def generate_all_synthetic() -> dict[str, pd.DataFrame]:
    """Generates synthetic data for all series. Used as full fallback."""
    result = {}
    for name, (start, drift, vol, seed) in SYNTHETIC_PARAMS.items():
        result[name] = generate_synthetic_series(36, start, drift, vol, seed)
    return result


# ─── NEWS GENERATOR ───────────────────────────────────────────────────────────

def generate_synthetic_news(n: int = 50) -> list[dict]:
    """
    Generates realistic synthetic news headlines for all 4 challenge materials.
    Pre-labelled with FinBERT-style sentiment for when HuggingFace API is unavailable.
    """
    rng = random.Random(42)
    today = datetime.date.today()

    templates = [
        # (headline_template, material, finbert_label, score, magnitude)
        ("LME aluminium hits {n}-month {dir} on energy cost {move}", "aluminium", "negative", -0.72, "high"),
        ("European aluminium smelters cut output amid gas price {move}", "aluminium", "negative", -0.65, "high"),
        ("China aluminium exports surge {pct}%, pressuring LME prices", "aluminium", "negative", -0.58, "medium"),
        ("OPEC+ agrees {pct}% output cut, Brent rallies", "aluminium", "positive", 0.55, "medium"),
        ("Turkey PET capacity reduced by {pct}% following plant issues", "vpet", "positive", 0.68, "high"),
        ("PTA plant outage in China reduces global PET feedstock supply", "vpet", "positive", 0.80, "high"),
        ("EU imposes anti-dumping duties on Asian PET imports", "vpet", "positive", 0.62, "medium"),
        ("Asia PET exports surge amid weak local demand", "vpet", "negative", -0.55, "medium"),
        ("EU proposes stricter rPET content rules — {pct}% by 2027", "rpet", "positive", 0.75, "high"),
        ("Recycled PET supply tightens as collection rates plateau", "rpet", "positive", 0.60, "medium"),
        ("Spain barley harvest forecast cut by {pct}% on drought", "barley", "negative", -0.70, "high"),
        ("French wheat crop upgraded — bearish for barley prices", "barley", "negative", -0.50, "medium"),
        ("EU drought monitor raises alarm for Iberian cereal crops", "barley", "negative", -0.65, "high"),
        ("Record Australian barley harvest weighs on global prices", "barley", "negative", -0.45, "medium"),
        ("COT report: speculative net-long aluminium positions at {n}-year high", "aluminium", "positive", 0.60, "medium"),
        ("Red Sea disruptions push shipping rates up {pct}%", "aluminium", "negative", -0.48, "medium"),
        ("EU natural gas storage at {pct}% capacity — bearish for energy", "energy", "negative", -0.55, "medium"),
        ("Russian gas transit halted — EU TTF spikes {pct}%", "energy", "negative", -0.80, "high"),
        ("Brent crude drops {pct}% on demand concerns", "aluminium", "negative", -0.62, "medium"),
        ("MEG prices hit 18-month low on Asian oversupply", "vpet", "negative", -0.55, "medium"),
    ]

    news = []
    for i in range(n):
        tmpl, material, label, score, magnitude = rng.choice(templates)
        pct  = rng.randint(3, 18)
        n_   = rng.randint(2, 8)
        dir_ = rng.choice(["high", "low"])
        move = rng.choice(["surge", "increase", "spike", "decline", "drop"])
        headline = tmpl.format(pct=pct, n=n_, dir=dir_, move=move)
        days_ago = rng.randint(0, 60)
        date = (today - datetime.timedelta(days=days_ago)).isoformat()
        news.append({
            "date": date,
            "headline": headline,
            "source": rng.choice(["Reuters", "Bloomberg", "ICIS", "Fastmarkets", "FT", "Expana"]),
            "material": material,
            "finbert_label": label,
            "finbert_score": round(abs(score) + rng.uniform(-0.05, 0.05), 3),
            "score": round(score, 3),
            "magnitude": magnitude,
            "classified_by": "synthetic",    # "finbert" or "claude" when real
            "reasoning": None,                # Filled by Claude classifier
        })

    news.sort(key=lambda x: x["date"], reverse=True)
    return news


# ─── MASTER LOADER ────────────────────────────────────────────────────────────

def load_all_data(cache_dir: str = "data") -> dict:
    """
    Master data loader. Returns a dict with all series as DataFrames.

    Priority:
      1. Damm CSV (barley only)
      2. FRED live data
      3. Synthetic fallback
    """
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    cache_path = Path(cache_dir) / "fred_cache.json"

    # Try FRED first
    fred_data = {}

    # Check cache (refresh every 24h to avoid hammering FRED)
    if cache_path.exists():
        age = time.time() - cache_path.stat().st_mtime
        if age < 86400:   # Less than 24 hours old
            print("Using cached FRED data (< 24h old)")
            raw = json.loads(cache_path.read_text())
            for k, v in raw.items():
                df = pd.DataFrame(v)
                df["date"] = pd.to_datetime(df["date"])
                fred_data[k] = df
        else:
            fred_data = fetch_all_fred()
            _save_fred_cache(fred_data, cache_path)
    else:
        fred_data = fetch_all_fred()
        _save_fred_cache(fred_data, cache_path)

    # Fill any missing series with synthetic data
    synthetic = generate_all_synthetic()
    all_series = {}
    for name in SYNTHETIC_PARAMS:
        if name in fred_data and fred_data[name] is not None:
            all_series[name] = fred_data[name]
        else:
            all_series[name] = synthetic[name]
            print(f"  ℹ️  Using synthetic data for {name}")

    # Override barley with Damm's CSV if available
    damm_barley = load_damm_barley(f"{cache_dir}/barley_damm.csv")
    if damm_barley is not None:
        all_series["barley"] = damm_barley
        all_series["damm_barley_loaded"] = True
    else:
        all_series["damm_barley_loaded"] = False

    # Add vPET/rPET (derived from oil — no FRED series exists)
    all_series["vpet"] = _derive_vpet(all_series["oil"])
    all_series["rpet"] = _derive_rpet(all_series["vpet"])

    # News
    news_path = Path(cache_dir) / "news.json"
    if news_path.exists():
        all_series["news"] = json.loads(news_path.read_text())
    else:
        all_series["news"] = generate_synthetic_news(50)
        news_path.write_text(json.dumps(all_series["news"], indent=2))

    return all_series


def _derive_vpet(oil_df: pd.DataFrame) -> pd.DataFrame:
    """
    Derives vPET price from oil price.
    Formula: vPET ≈ oil * 8.5 + 180 (rough heuristic for EUR/tonne)
    Replace with real ICIS data when available.
    """
    df = oil_df.copy()
    df["value"] = (df["value"] * 8.5 + 180).round(1)
    return df


def _derive_rpet(vpet_df: pd.DataFrame) -> pd.DataFrame:
    """
    Derives rPET price from vPET.
    rPET ≈ vPET * 1.13 + regulatory_premium
    """
    df = vpet_df.copy()
    df["value"] = (df["value"] * 1.13 + 15).round(1)
    return df


def _save_fred_cache(data: dict, path: Path):
    """Saves FRED data to JSON cache."""
    try:
        serialisable = {}
        for k, df in data.items():
            if df is not None:
                df_copy = df.copy()
                df_copy["date"] = df_copy["date"].astype(str)
                serialisable[k] = df_copy.to_dict(orient="records")
        path.write_text(json.dumps(serialisable, indent=2))
    except Exception as e:
        print(f"  [Cache] Could not save: {e}")


if __name__ == "__main__":
    data = load_all_data()
    print("\n=== Data loaded ===")
    for k, v in data.items():
        if isinstance(v, pd.DataFrame):
            latest = v.iloc[-1]
            print(f"  {k:<14} {len(v):>4} rows  latest: {latest['value']:.2f} ({latest['date'].date()})")
        elif k == "news":
            print(f"  {'news':<14} {len(v):>4} items")
        else:
            print(f"  {k:<14} {v}")
