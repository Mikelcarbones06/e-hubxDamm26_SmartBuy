"""
SmartBuy — Recommendation Engine
==================================
Produces the 4 official actions required by the challenge:
  BUY     — buy now, prices expected to rise
  WAIT    — prices expected to fall, delay purchase
  HEDGE   — lock in current price via forward contract
  MONITOR — insufficient signal, keep watching

Also produces:
  score         — 0-100 opportunity/risk score
  horizon       — suggested timing (e.g. "within 14 days")
  hedge_horizon — how long to hedge if HEDGE recommended
  drivers       — what is pushing price up or down
  signals       — plain English list of evidence
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional

from features import (
    add_price_features, compute_price_forecast,
    detect_anomalies, find_historical_analogues, compute_news_sentiment
)
from data_ingestion import MATERIALS


# ─── OUTPUT DATACLASS ─────────────────────────────────────────────────────────

@dataclass
class Recommendation:
    material_id:    str
    material_name:  str
    action:         str         # BUY | WAIT | HEDGE | MONITOR
    score:          int         # 0-100
    confidence:     str         # HIGH | MEDIUM | LOW
    horizon:        str         # "within 7 days" | "wait 2-3 weeks" etc.
    hedge_horizon:  Optional[str]  # "hedge for 60 days" — only if action=HEDGE
    drivers_up:     list[str]   # What's pushing price UP
    drivers_down:   list[str]   # What's pushing price DOWN
    signals:        list[str]   # All evidence, plain English
    score_components: dict      # Sub-scores for transparency
    forecast:       dict
    anomalies:      list
    analogues:      list
    news_sentiment: dict
    composite_signal: dict      # From news_classifier


# ─── SCORE WEIGHTS ────────────────────────────────────────────────────────────
# Total = 100 points
# Adjust weights if you want to emphasise different factors

WEIGHTS = {
    "price_trend":    40,   # Direction and strength of price trend
    "market_pressure": 25,  # Technical indicators (z-score, momentum, Bollinger)
    "news_composite":  20,  # News sentiment + composite signal
    "historical":      15,  # Historical analogue outcomes
}


# ─── HORIZON TABLES ───────────────────────────────────────────────────────────

def _buy_horizon(score: int, forecast_pct: float, lead_time: int) -> str:
    """Suggests a purchase horizon based on score and lead time."""
    if score >= 80:
        days = max(lead_time, 3)
        return f"within {days} days (urgent — order to cover lead time)"
    elif score >= 65:
        return "within 7–14 days"
    elif score >= 50:
        return "within 2–3 weeks, monitor daily"
    else:
        return "no urgency — reassess in 1 week"


def _wait_horizon(forecast_pct: float) -> str:
    """Suggests how long to wait before reassessing."""
    if forecast_pct < -5:
        return "wait 3–4 weeks — strong downtrend expected"
    elif forecast_pct < -2:
        return "wait 2–3 weeks — mild softening expected"
    else:
        return "wait 1–2 weeks, reassess when trend clarifies"


def _hedge_horizon(score: int, material_id: str) -> str:
    """Suggests how long to hedge for."""
    from data_ingestion import MATERIALS
    max_forward = {
        "aluminium": 90,
        "vpet": 90,
        "rpet": 90,
        "barley": 180,
        "energy": 30,
    }
    max_d = max_forward.get(material_id, 60)

    if score >= 75:
        days = min(max_d, 90)
        return f"hedge {days} days forward — high conviction uptrend"
    elif score >= 60:
        days = min(max_d, 60)
        return f"hedge {days} days forward — moderate conviction"
    else:
        days = min(max_d, 30)
        return f"partial hedge {days} days — uncertainty remains"


# ─── MAIN SCORING FUNCTION ────────────────────────────────────────────────────

def compute_recommendation(
    price_df,
    news: list[dict],
    composite_signal: dict,
    material_id: str,
) -> Recommendation:
    """
    Builds the full recommendation for one material.

    Inputs:
      price_df         — DataFrame with 'date' and 'value' columns
      news             — list of classified headline dicts
      composite_signal — output of news_classifier.compute_composite_signal()
      material_id      — one of: aluminium, vpet, rpet, barley, energy
    """
    mat_info = MATERIALS.get(material_id, {})
    lead_time = mat_info.get("lead_time_days", 14)

    # ── Features ──
    df_feat  = add_price_features(price_df)
    forecast = compute_price_forecast(price_df)
    anomalies = detect_anomalies(price_df)
    analogues = find_historical_analogues(price_df)
    sentiment = compute_news_sentiment(news, material_id)
    latest    = df_feat.dropna(subset=["z30"]).iloc[-1] if not df_feat.dropna(subset=["z30"]).empty else df_feat.iloc[-1]

    drivers_up   = []
    drivers_down = []
    signals      = []
    components   = {}

    # ── 1. PRICE TREND (40 pts) ───────────────────────────────────────────────
    pct30 = forecast["forecast_30d_pct"]
    r2    = forecast["r2"]

    if pct30 > 6:
        pt = 38; signals.append(f"Strong uptrend forecast: +{pct30:.1f}% in 30 days (R²={r2:.2f})")
        drivers_up.append(f"Price trending up +{pct30:.1f}% (30-day forecast)")
    elif pct30 > 3:
        pt = 30; signals.append(f"Mild uptrend: +{pct30:.1f}% forecast in 30 days")
        drivers_up.append(f"Mild upward trend (+{pct30:.1f}%)")
    elif pct30 < -6:
        pt = 5; signals.append(f"Strong downtrend: {pct30:.1f}% forecast in 30 days")
        drivers_down.append(f"Price trending down {pct30:.1f}%")
    elif pct30 < -3:
        pt = 12; signals.append(f"Mild downtrend: {pct30:.1f}% forecast in 30 days")
        drivers_down.append(f"Softening price trend ({pct30:.1f}%)")
    else:
        pt = 20; signals.append(f"Flat price trend ({pct30:+.1f}% forecast)")

    # Z-score adjustment: are we buying cheap or expensive?
    z30 = float(latest.get("z30", 0)) if not np.isnan(float(latest.get("z30", 0) or 0)) else 0
    if z30 < -1.5:
        pt = min(40, pt + 8)
        signals.append(f"Price is {abs(z30):.1f}σ below 30-day average — attractive entry point")
        drivers_up.append("Current price below recent average (discount opportunity)")
    elif z30 > 1.5:
        pt = max(0, pt - 8)
        signals.append(f"Price is {z30:.1f}σ above 30-day average — buying at premium")
        drivers_down.append("Price above recent average (elevated entry cost)")

    components["price_trend"] = min(40, max(0, pt))

    # ── 2. MARKET PRESSURE (25 pts) ───────────────────────────────────────────
    mp = 12  # Neutral start

    momentum = float(latest.get("momentum", 0)) if not np.isnan(float(latest.get("momentum", 0) or 0)) else 0
    current  = float(latest.get("value", 0))
    if current > 0:
        mom_pct = momentum / current * 100
        if mom_pct > 2:
            mp += 7
            signals.append(f"Positive momentum: 7-period MA above 30-period MA by {mom_pct:.1f}%")
            drivers_up.append("Short-term momentum positive")
        elif mom_pct < -2:
            mp -= 7
            signals.append(f"Negative momentum: price weakening ({mom_pct:.1f}%)")
            drivers_down.append("Short-term momentum negative")

    bb_pct = float(latest.get("bb_pct", 0.5)) if not np.isnan(float(latest.get("bb_pct", 0.5) or 0.5)) else 0.5
    if bb_pct < 0.2:
        mp += 5
        signals.append("Price near lower Bollinger band — statistically cheap")
        drivers_up.append("Price at lower Bollinger band boundary")
    elif bb_pct > 0.8:
        mp -= 5
        signals.append("Price near upper Bollinger band — statistically expensive")
        drivers_down.append("Price at upper Bollinger band — overextended")

    for a in anomalies:
        if a["direction"] == "drop":
            mp += 4
            signals.append(f"Price anomaly detected: {abs(a['z_score']):.1f}σ drop on {a['date']} — potential buy signal")
        else:
            mp -= 3
            signals.append(f"Price anomaly detected: {a['z_score']:.1f}σ spike — elevated entry risk")

    components["market_pressure"] = min(25, max(0, mp))

    # ── 3. NEWS COMPOSITE (20 pts) ────────────────────────────────────────────
    comp = composite_signal
    sent_score = sentiment["score"]

    if comp["composite"] == "STRUCTURAL_SHIFT":
        if comp["direction"] == "bullish":
            ns = 18
            signals.append(f"STRUCTURAL SHIFT: {comp['high_magnitude_count']} major supply/demand events in {comp['signal_count']} recent headlines")
            drivers_up.append("Multiple major market events signalling supply tightening")
        else:
            ns = 4
            signals.append(f"STRUCTURAL SHIFT (bearish): {comp['high_magnitude_count']} major bearish events detected")
            drivers_down.append("Multiple major bearish events in recent news")
    elif comp["composite"] == "TREND":
        ns = 13 if comp["direction"] == "bullish" else 7
        signals.append(f"News trend: {comp['direction']} ({comp['bullish_count']} bullish vs {comp['bearish_count']} bearish signals)")
        if comp["direction"] == "bullish":
            drivers_up.append("News sentiment trending bullish")
        else:
            drivers_down.append("News sentiment trending bearish")
    else:
        ns = 10 + int(sent_score * 5)
        signals.append(f"News sentiment: {sentiment['direction']} (score: {sent_score:+.2f}, {sentiment['count']} recent items)")

    components["news_composite"] = min(20, max(0, ns))

    # ── 4. HISTORICAL ANALOGUES (15 pts) ──────────────────────────────────────
    ha = 7  # Neutral
    if analogues:
        up_count  = sum(1 for a in analogues if a["outcome_direction"] == "up")
        avg_out   = np.mean([a["outcome_30d_pct"] for a in analogues])
        if avg_out > 4:
            ha = 14
            signals.append(f"Historical analogues: similar market conditions led to +{avg_out:.1f}% avg over 30 days ({up_count}/{len(analogues)} periods up)")
            drivers_up.append(f"Historical precedent: +{avg_out:.1f}% avg in similar conditions")
        elif avg_out < -4:
            ha = 2
            signals.append(f"Historical analogues: similar conditions led to {avg_out:.1f}% avg — caution")
            drivers_down.append(f"Historical precedent: {avg_out:.1f}% in similar conditions")
        else:
            ha = 7
            signals.append(f"Historical analogues: mixed outcomes ({up_count}/{len(analogues)} up, avg {avg_out:+.1f}%)")

    components["historical"] = min(15, max(0, ha))

    # ── TOTAL SCORE ───────────────────────────────────────────────────────────
    total = sum(components.values())
    total = max(0, min(100, total))

    # ── ACTION MAPPING ────────────────────────────────────────────────────────
    # The 4 official actions from the challenge brief
    #
    # BUY     — high score + uptrend → buy now before prices rise
    # HEDGE   — moderate-high score but uncertain → lock in current price
    # WAIT    — low score + downtrend → prices expected to fall
    # MONITOR — insufficient signal → gather more data first
    #
    # Special override: if composite signal is STRUCTURAL_SHIFT bullish,
    # always at least HEDGE regardless of score

    structural_bullish = (
        comp["composite"] == "STRUCTURAL_SHIFT"
        and comp["direction"] == "bullish"
    )

    if total >= 72 or (total >= 60 and structural_bullish):
        action = "BUY"
        confidence = "HIGH" if total >= 82 else "MEDIUM"
        horizon = _buy_horizon(total, pct30, lead_time)
        hedge_horizon = None

    elif total >= 55 or structural_bullish:
        action = "HEDGE"
        confidence = "MEDIUM"
        horizon = f"Hedge within {lead_time} days to secure current price"
        hedge_horizon = _hedge_horizon(total, material_id)

    elif total <= 30:
        action = "WAIT"
        confidence = "HIGH" if total <= 20 else "MEDIUM"
        horizon = _wait_horizon(pct30)
        hedge_horizon = None

    else:
        action = "MONITOR"
        confidence = "LOW"
        horizon = "Reassess in 5–7 days as signals develop"
        hedge_horizon = None

    return Recommendation(
        material_id=material_id,
        material_name=mat_info.get("name", material_id),
        action=action,
        score=total,
        confidence=confidence,
        horizon=horizon,
        hedge_horizon=hedge_horizon,
        drivers_up=drivers_up,
        drivers_down=drivers_down,
        signals=signals,
        score_components=components,
        forecast=forecast,
        anomalies=anomalies,
        analogues=analogues,
        news_sentiment=sentiment,
        composite_signal=comp,
    )


def recommendation_to_dict(rec: Recommendation) -> dict:
    """Converts a Recommendation to a JSON-serialisable dict."""
    return {
        "material_id":      rec.material_id,
        "material_name":    rec.material_name,
        "action":           rec.action,
        "score":            rec.score,
        "confidence":       rec.confidence,
        "horizon":          rec.horizon,
        "hedge_horizon":    rec.hedge_horizon,
        "drivers_up":       rec.drivers_up,
        "drivers_down":     rec.drivers_down,
        "signals":          rec.signals,
        "score_components": rec.score_components,
        "forecast":         rec.forecast,
        "anomalies":        rec.anomalies,
        "analogues":        rec.analogues,
        "news_sentiment":   {
            k: v for k, v in rec.news_sentiment.items()
            if k not in ("top_bullish", "top_bearish")
        },
        "composite_signal": {
            k: v for k, v in rec.composite_signal.items()
            if k != "top_headlines"
        },
    }
