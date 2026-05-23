"""
SmartBuy — FastAPI Server
==========================
Endpoints:
  GET  /api/dashboard          — all materials, scores, news
  GET  /api/material/{id}      — deep data for one material
  GET  /api/narrative/{id}     — AI narrative for one material
  GET  /api/sources             — documented data sources
  POST /api/chat               — procurement Q&A
  POST /api/scenario           — what-if analysis
"""

import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from data_ingestion import load_all_data, MATERIALS
from features import add_price_features, compute_news_sentiment
from models import compute_recommendation, recommendation_to_dict
from news_classifier import classify_headlines, compute_composite_signal
from explainer import generate_narrative, answer_question, analyse_scenario
from sources import get_all_sources, get_sources_for_material

app = FastAPI(title="SmartBuy API", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Load data once on startup ──────────────────────────────────────────────────
print("\nSmartBuy starting up...")
_data = load_all_data()
_news = _data.get("news", [])
_classified_news = classify_headlines(_news, use_claude_for_top_n=3)

# Build recommendations for all materials
_recs = {}
for mat_id in MATERIALS:
    if mat_id not in _data:
        continue
    price_df = _data[mat_id]
    composite = compute_composite_signal(_classified_news, mat_id)
    rec = compute_recommendation(price_df, _classified_news, composite, mat_id)
    _recs[mat_id] = recommendation_to_dict(rec)

print(f"\nRecommendations ready for: {list(_recs.keys())}")


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _get_chart_data(mat_id: str, n: int = 36) -> list[dict]:
    """Returns chart-ready price data for a material."""
    if mat_id not in _data:
        return []
    df = add_price_features(_data[mat_id])
    tail = df.tail(n).copy()
    tail["date"] = tail["date"].astype(str)
    cols = ["date", "value", "ma7", "ma30", "bb_upper", "bb_lower"]
    cols = [c for c in cols if c in tail.columns]
    return tail[cols].fillna(0).round(2).to_dict(orient="records")

def _get_top_news(mat_id: str, n: int = 8) -> list[dict]:
    """Returns top classified headlines for a material."""
    relevant = [
        h for h in _classified_news
        if h.get("material") in (mat_id, "macro")
    ]
    return sorted(relevant, key=lambda x: abs(x.get("score", 0)), reverse=True)[:n]


# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@app.get("/api/dashboard")
def get_dashboard():
    """Returns summary cards for all materials — used for the overview page."""
    summary = {}
    for mat_id, rec in _recs.items():
        summary[mat_id] = {
            "name":       rec["material_name"],
            "action":     rec["action"],
            "score":      rec["score"],
            "confidence": rec["confidence"],
            "horizon":    rec["horizon"],
            "hedge_horizon": rec.get("hedge_horizon"),
            "forecast_30d_pct": rec["forecast"]["forecast_30d_pct"],
            "current_price":    rec["forecast"]["current_price"],
            "top_driver_up":   rec["drivers_up"][0] if rec["drivers_up"] else None,
            "top_driver_down": rec["drivers_down"][0] if rec["drivers_down"] else None,
            "composite_signal": rec["composite_signal"]["composite"],
        }

    top_news = sorted(
        [h for h in _classified_news if abs(h.get("score", 0)) > 0.4],
        key=lambda x: abs(x["score"]), reverse=True
    )[:10]

    return {
        "materials": summary,
        "top_news": top_news,
        "damm_barley_loaded": _data.get("damm_barley_loaded", False),
    }


@app.get("/api/material/{mat_id}")
def get_material(mat_id: str):
    """Full data for one material: recommendation, chart, news, sources."""
    if mat_id not in _recs:
        raise HTTPException(404, f"Material '{mat_id}' not found. Valid: {list(_recs.keys())}")

    return {
        "recommendation": _recs[mat_id],
        "chart_data":     _get_chart_data(mat_id),
        "news":           _get_top_news(mat_id),
        "sources":        get_sources_for_material(mat_id),
    }


@app.get("/api/narrative/{mat_id}")
def get_narrative(mat_id: str):
    """Generates an AI narrative for a material. Uses Anthropic API."""
    if mat_id not in _recs:
        raise HTTPException(404, f"Unknown material: {mat_id}")
    top_news = _get_top_news(mat_id, 4)
    try:
        text = generate_narrative(_recs[mat_id], top_news)
    except Exception as e:
        text = f"[Narrative unavailable: {e}]"
    return {"narrative": text, "material": mat_id}


@app.get("/api/sources")
def get_sources():
    """Returns all documented data sources — required by challenge checklist."""
    return get_all_sources()


class ChatRequest(BaseModel):
    question: str
    history: list[dict] = []

@app.post("/api/chat")
def chat(req: ChatRequest):
    """Procurement Q&A using Claude."""
    try:
        answer = answer_question(req.question, _recs, req.history)
    except Exception as e:
        answer = f"[Error: {e}]"
    return {"answer": answer}


class ScenarioRequest(BaseModel):
    description: str
    material_id: str = "aluminium"

@app.post("/api/scenario")
def scenario(req: ScenarioRequest):
    """What-if scenario analysis."""
    if req.material_id not in _recs:
        raise HTTPException(404)
    try:
        analysis = analyse_scenario(req.description, req.material_id, _recs[req.material_id])
    except Exception as e:
        analysis = f"[Error: {e}]"
    return {"analysis": analysis, "material_id": req.material_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
