"""
SmartBuy — Live Price Fetcher
==============================
Fetches today's commodity prices from multiple free sources.
Falls back gracefully if any source fails.

Sources tried in order:
  1. yfinance library (most reliable, wraps Yahoo Finance properly)
  2. Stooq (free, no key needed, works globally)
  3. Hardcoded Cala-verified prices (always works as last resort)

HOW TO RUN:
  pip install yfinance
  python3 live_prices.py
"""

import json
import datetime
from pathlib import Path


# ─── CALA-VERIFIED FALLBACK PRICES ───────────────────────────────────────────
# These came directly from Cala.ai during the hackathon session.
# Use as last resort if all live fetches fail.
# Update these manually if you get fresher data.

CALA_VERIFIED_PRICES = {
    "aluminium": {
        "price": 3314.25,
        "unit": "USD/tonne",
        "source": "Cala.ai — Mining.com, mid-May 2026",
        "eur_per_tonne": round(3314.25 / 1.08, 1),
    },
    "vpet": {
        "price": 1170.0,
        "unit": "USD/tonne",
        "source": "Cala.ai — Europe May 2025 (stale — update if possible)",
        "eur_per_tonne": round(1170.0 / 1.08, 1),
    },
    "rpet": {
        "price": round(1170.0 * 1.13 + 15, 1),
        "unit": "EUR/tonne",
        "source": "Derived from vPET",
        "eur_per_tonne": round(1170.0 * 1.13 + 15, 1),
    },
    "barley": {
        "price": 210.0,
        "unit": "USD/tonne",
        "source": "Cala.ai — global benchmark midpoint 2025",
        "eur_per_tonne": round(210.0 / 1.08, 1),
    },
    "oil": {
        "price": 65.0,
        "unit": "USD/barrel",
        "source": "Estimated — update with live data",
        "eur_per_tonne": None,
    },
    "eurusd": {
        "price": 1.08,
        "unit": "USD per EUR",
        "source": "Approximate",
        "eur_per_tonne": None,
    },
}


# ─── METHOD 1: yfinance ───────────────────────────────────────────────────────

def fetch_via_yfinance():
    """Uses the yfinance library which handles Yahoo Finance auth properly."""
    try:
        import yfinance as yf
    except ImportError:
        print("  [yfinance] Not installed. Run: pip3 install yfinance")
        return None

    SYMBOLS = {
        "aluminium": "ALI=F",
        "oil":       "BZ=F",
        "wheat":     "ZW=F",
        "nat_gas":   "NG=F",
        "sugar":     "SB=F",
        "eurusd":    "EURUSD=X",
        "corn":      "ZC=F",
    }

    results = {}
    for mat, sym in SYMBOLS.items():
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="2d")
            if not hist.empty:
                price = float(hist["Close"].dropna().iloc[-1])
                results[mat] = {
                    "price":      price,
                    "symbol":     sym,
                    "source":     "Yahoo Finance via yfinance",
                    "fetched_at": datetime.datetime.now().isoformat(),
                }
                print(f"  ✅ {mat:<14} {sym:<12} {price:.4f}")
            else:
                print(f"  ❌ {mat:<14} {sym:<12} no data")
        except Exception as e:
            print(f"  ❌ {mat:<14} {sym:<12} {str(e)[:40]}")

    return results if results else None


# ─── METHOD 2: Stooq ─────────────────────────────────────────────────────────

def fetch_via_stooq():
    """
    Stooq.com is a free financial data site with no API key.
    Works by fetching a simple CSV URL.
    """
    import urllib.request

    # Stooq symbols for commodities
    STOOQ_SYMBOLS = {
        "oil":    "CL.F",      # WTI Crude
        "wheat":  "W.F",       # Wheat futures
        "corn":   "C.F",       # Corn futures
        "eurusd": "EURUSD",    # EUR/USD
    }

    results = {}
    for mat, sym in STOOQ_SYMBOLS.items():
        url = f"https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcv&h&e=csv"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                lines = r.read().decode().strip().split("\n")
            if len(lines) >= 2:
                parts = lines[1].split(",")
                price = float(parts[4])  # Close price
                results[mat] = {
                    "price":      price,
                    "symbol":     sym,
                    "source":     "Stooq.com",
                    "fetched_at": datetime.datetime.now().isoformat(),
                }
                print(f"  ✅ {mat:<14} {sym:<12} {price:.4f}")
            else:
                print(f"  ❌ {mat:<14} {sym:<12} empty response")
        except Exception as e:
            print(f"  ❌ {mat:<14} {sym:<12} {str(e)[:40]}")

    return results if results else None


# ─── UNIT CONVERTERS ─────────────────────────────────────────────────────────

def convert_to_eur_tonne(prices, eurusd=1.08):
    """Converts raw futures prices to EUR/tonne where possible."""
    converted = {}
    eurusd_rate = prices.get("eurusd", {}).get("price", eurusd)

    CONVERSIONS = {
        # symbol: multiplier to get USD/tonne
        "aluminium": lambda p: p / eurusd_rate,           # Already USD/tonne
        "wheat":     lambda p: p * 36.7437 / eurusd_rate, # bushel -> tonne
        "corn":      lambda p: p * 39.368 / eurusd_rate,  # bushel -> tonne
        "sugar":     lambda p: p * 2204.6 / eurusd_rate,  # lb -> tonne
        "oil":       lambda p: p / eurusd_rate,            # USD/barrel (keep)
        "nat_gas":   lambda p: p / eurusd_rate,            # USD/MMBtu (keep)
    }

    for mat, data in prices.items():
        if mat == "eurusd":
            converted[mat] = {**data, "eur_per_tonne": None}
            continue
        conv = CONVERSIONS.get(mat)
        eur = round(conv(data["price"]), 1) if conv else None
        converted[mat] = {**data, "eur_per_tonne": eur}

    # Derive vPET and rPET from oil
    if "oil" in converted:
        oil_usd = converted["oil"]["price"]
        oil_eur = oil_usd / eurusd_rate
        vpet = round(oil_eur * 8.5 + 180, 1)
        rpet = round(vpet * 1.13 + 15, 1)
        converted["vpet"] = {
            "price": vpet, "symbol": "DERIVED", "eur_per_tonne": vpet,
            "source": f"Derived from oil ({oil_usd:.1f} USD/bbl)",
            "fetched_at": datetime.datetime.now().isoformat(),
        }
        converted["rpet"] = {
            "price": rpet, "symbol": "DERIVED", "eur_per_tonne": rpet,
            "source": "Derived from vPET x1.13 + 15",
            "fetched_at": datetime.datetime.now().isoformat(),
        }

    return converted


# ─── MASTER FETCHER ───────────────────────────────────────────────────────────

def fetch_all_live_prices():
    """
    Tries multiple sources in order. Returns best available prices.
    Always returns something — worst case uses Cala-verified prices.
    """
    print("\n📡 Fetching live prices...")
    print("-" * 55)

    # Method 1: yfinance
    print("Trying yfinance...")
    prices = fetch_via_yfinance()

    # Method 2: Stooq fallback
    if not prices:
        print("\nTrying Stooq...")
        prices = fetch_via_stooq()

    # Method 3: Cala-verified hardcoded
    if not prices:
        print("\n⚠️  All live sources failed — using Cala-verified prices")
        print("   These are verified but may be weeks/months old.")
        result = {}
        for mat, data in CALA_VERIFIED_PRICES.items():
            result[mat] = {
                "price":      data["price"],
                "symbol":     "CALA_VERIFIED",
                "source":     data["source"],
                "eur_per_tonne": data.get("eur_per_tonne"),
                "fetched_at": datetime.datetime.now().isoformat(),
            }
            print(f"  📌 {mat:<14} {data['price']:>10.1f} {data['unit']}")
        return result

    # Convert units
    eurusd = prices.get("eurusd", {}).get("price", 1.08)
    converted = convert_to_eur_tonne(prices, eurusd)

    print("-" * 55)
    print(f"  EUR/USD: {eurusd:.4f}")
    print("\n  EUR/tonne equivalents:")
    for mat, data in converted.items():
        eur = data.get("eur_per_tonne")
        if eur:
            print(f"    {mat:<14} {eur:>8.1f} EUR/t")

    return converted


def save_prices(prices, path="data/live_prices.json"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(prices, f, indent=2)
    print(f"\n  💾 Saved to {path}")


def load_prices(path="data/live_prices.json"):
    p = Path(path)
    if not p.exists():
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return None


if __name__ == "__main__":
    prices = fetch_all_live_prices()
    save_prices(prices)
    print("\n✅ Done. Prices saved to data/live_prices.json")