"""
SmartBuy — Feature Engineering
================================
Builds model-ready signals from raw price series.
Works for all materials: aluminium, vPET, rPET, barley, energy.
"""

import numpy as np
import pandas as pd
import datetime
from typing import Optional


def add_price_features(df: pd.DataFrame, col: str = "value") -> pd.DataFrame:
    """
    Adds technical indicators to any price DataFrame.

    Indicators added:
      ma7, ma30         — 7-day and 30-day moving averages
      std30             — 30-day rolling standard deviation
      z30               — z-score vs 30-day mean (how cheap/expensive right now)
      pct7d, pct30d     — percentage change over 7 and 30 periods
      momentum          — MA7 minus MA30 (positive = uptrend)
      bb_upper/lower    — Bollinger bands (MA30 ± 2σ)
      bb_pct            — where price sits within Bollinger bands (0=bottom, 1=top)
    """
    df = df.copy().sort_values("date").reset_index(drop=True)

    df[f"ma7"]    = df[col].rolling(7, min_periods=3).mean()
    df[f"ma30"]   = df[col].rolling(30, min_periods=10).mean()
    df[f"std30"]  = df[col].rolling(30, min_periods=10).std()
    df[f"z30"]    = (df[col] - df["ma30"]) / df["std30"].replace(0, np.nan)
    df[f"pct7d"]  = df[col].pct_change(7)
    df[f"pct30d"] = df[col].pct_change(30)
    df[f"momentum"] = df["ma7"] - df["ma30"]

    df["bb_upper"] = df["ma30"] + 2 * df["std30"]
    df["bb_lower"] = df["ma30"] - 2 * df["std30"]
    bb_range = (df["bb_upper"] - df["bb_lower"]).replace(0, np.nan)
    df["bb_pct"] = (df[col] - df["bb_lower"]) / bb_range

    return df


def compute_price_forecast(df: pd.DataFrame, horizon_periods: int = 30) -> dict:
    """
    Linear trend forecast over the last 60 periods.
    Returns price change % and EUR/unit for 7 and 30 periods ahead.

    Not a crystal ball — just the current trend extrapolated.
    Reliable R² > 0.5 means the trend is consistent.
    """
    series = df["value"].dropna().tail(60).values
    if len(series) < 10:
        return {"trend": "flat", "forecast_30d_pct": 0, "r2": 0}

    x = np.arange(len(series), dtype=float)
    coeffs = np.polyfit(x, series, 1)
    slope = coeffs[0]

    predicted = np.polyval(coeffs, x)
    ss_res = ((series - predicted) ** 2).sum()
    ss_tot = ((series - series.mean()) ** 2).sum()
    r2 = max(0.0, 1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    current = series[-1]
    f7  = slope * 7
    f30 = slope * 30

    pct7  = round(f7  / current * 100, 2) if current else 0
    pct30 = round(f30 / current * 100, 2) if current else 0

    trend = "flat"
    if abs(pct30) >= 1.5:
        trend = "up" if pct30 > 0 else "down"

    return {
        "current_price":    round(current, 2),
        "forecast_7d_pct":  pct7,
        "forecast_30d_pct": pct30,
        "forecast_7d_abs":  round(f7, 2),
        "forecast_30d_abs": round(f30, 2),
        "trend":            trend,
        "r2":               round(r2, 3),
        "slope_per_period": round(slope, 4),
    }


def detect_anomalies(df: pd.DataFrame, z_threshold: float = 2.0) -> list[dict]:
    """
    Detects price anomalies in the last 14 periods.
    An anomaly = price more than z_threshold standard deviations from 30-period mean.

    Why this matters: anomalies often precede larger moves.
    A drop anomaly = potential buying opportunity.
    A spike anomaly = might be too late to buy.
    """
    df_feat = add_price_features(df)
    recent = df_feat.dropna(subset=["z30"]).tail(14)
    anomalies = []

    for _, row in recent.iterrows():
        z = row["z30"]
        if abs(z) >= z_threshold:
            anomalies.append({
                "date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"])[:10],
                "value": round(row["value"], 2),
                "z_score": round(z, 2),
                "direction": "spike" if z > 0 else "drop",
                "signal": "bearish_entry" if z > 0 else "bullish_entry",
            })

    return anomalies


def find_historical_analogues(df: pd.DataFrame, n: int = 3) -> list[dict]:
    """
    Finds the N most similar historical 30-period windows to the current one.

    What "similar" means: oil/commodity trajectory over the last 30 periods
    matches the current trajectory (via Euclidean distance on feature vectors).

    Returns what happened to prices in the 30 periods AFTER each analogue.
    This is the "comparison with historical episodes" the challenge requires.
    """
    df_feat = add_price_features(df)
    feature_cols = ["pct30d", "z30", "momentum"]

    valid = df_feat.dropna(subset=feature_cols).reset_index(drop=True)
    if len(valid) < 60:
        return []

    current = valid[feature_cols].iloc[-1].values
    hist = valid[feature_cols].iloc[:-30]

    if len(hist) == 0:
        return []

    distances = np.sqrt(((hist.values - current) ** 2).sum(axis=1))
    top_idx = np.argsort(distances)[:n]

    analogues = []
    for idx in top_idx:
        row = valid.iloc[int(idx)]
        future_idx = min(int(idx) + 30, len(df) - 1)
        current_price = df["value"].iloc[int(idx)]
        future_price  = df["value"].iloc[future_idx]
        outcome_pct = round((future_price - current_price) / current_price * 100, 1) if current_price else 0

        analogues.append({
            "date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"])[:10],
            "price_at_time": round(float(current_price), 2),
            "outcome_30d_pct": outcome_pct,
            "outcome_direction": "up" if outcome_pct > 0 else "down",
            "distance": round(float(distances[idx]), 4),
            "pct30d_at_time": round(float(row["pct30d"]) * 100, 1),
            "z30_at_time": round(float(row["z30"]), 2),
        })

    return analogues


def compute_news_sentiment(news: list[dict], material: str, window_days: int = 30) -> dict:
    """Aggregates news sentiment for a material over the last window_days."""
    cutoff = (datetime.date.today() - datetime.timedelta(days=window_days)).isoformat()
    relevant = [
        n for n in news
        if n.get("material") in (material, "macro")
        and n.get("date", "") >= cutoff
        and n.get("score") is not None
    ]

    if not relevant:
        return {"score": 0.0, "count": 0, "direction": "neutral"}

    avg = sum(n["score"] for n in relevant) / len(relevant)
    return {
        "score": round(avg, 3),
        "count": len(relevant),
        "direction": "bullish" if avg > 0.1 else "bearish" if avg < -0.1 else "neutral",
        "top_bullish": sorted([n for n in relevant if n["score"] > 0.3], key=lambda x: x["score"], reverse=True)[:3],
        "top_bearish": sorted([n for n in relevant if n["score"] < -0.3], key=lambda x: x["score"])[:3],
    }
