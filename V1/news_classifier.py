"""
SmartBuy — News Classifier
===========================
Two-layer classification pipeline:

Layer 1 — HuggingFace FinBERT (fast, cheap, uses HF credits)
  • Classifies every headline as positive/negative/neutral
  • Cost: ~$0.0001 per headline
  • Speed: ~200ms per call
  • Use: filter and score all headlines

Layer 2 — Claude (slower, expensive, smart)
  • Only called for high-magnitude headlines (|score| > 0.5)
  • Explains WHICH materials are affected and WHY
  • Adds supply chain reasoning specific to Damm
  • Cost: ~$0.01 per headline

Together: FinBERT does the volume work cheaply,
Claude adds the explainability that judges will evaluate.
"""

import os
import json
import hashlib
import datetime
import feedparser       # pip install feedparser
import requests
from pathlib import Path

import anthropic


# ─── CONFIGURATION ────────────────────────────────────────────────────────────

# HuggingFace token — get free from huggingface.co/settings/tokens
# This is WHERE your HuggingFace credits get used
HF_TOKEN = os.getenv("HF_TOKEN", "")

# FinBERT endpoint on HuggingFace Inference API
# ProsusAI/finbert — trained specifically on financial news
# Returns: [{"label": "positive/negative/neutral", "score": 0.0-1.0}]
FINBERT_URL = "https://api-inference.huggingface.co/models/ProsusAI/finbert"

# Cache file — prevents re-classifying the same headline twice
CACHE_PATH = Path("data/news_cache.json")

# Only send to Claude if FinBERT confidence is above this threshold
# AND magnitude is high enough to matter
CLAUDE_THRESHOLD = 0.55

# RSS feed queries — one per material
# Google News RSS is free, real-time, no API key needed
RSS_QUERIES = {
    "aluminium": [
        "aluminium price LME supply",
        "aluminium smelter capacity Europe",
        "LME aluminium futures",
    ],
    "vpet": [
        "PET plastic price Europe ICIS",
        "Turkey PET export supply",
        "PTA MEG price petrochemical",
    ],
    "rpet": [
        "recycled PET rPET Europe regulation",
        "EU packaging recycled content mandate",
    ],
    "barley": [
        "barley price Europe supply",
        "EU cereal crop harvest forecast",
        "Spain drought barley wheat",
    ],
    "energy": [
        "EU natural gas TTF price",
        "European energy price industrial",
        "OMIP Spain electricity price",
    ],
    "macro": [
        "Brent crude oil OPEC supply",
        "Red Sea shipping disruption freight",
        "Baltic Dry Index shipping cost",
    ],
}


# ─── CACHE ────────────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    """Loads the classification cache from disk."""
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict):
    """Saves the classification cache to disk."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def _headline_key(headline: str) -> str:
    """Creates a stable cache key for a headline."""
    return hashlib.md5(headline.lower().strip().encode()).hexdigest()[:12]


# ─── RSS FETCHER ──────────────────────────────────────────────────────────────

def fetch_news_from_rss(max_per_query: int = 5) -> list[dict]:
    """
    Fetches real headlines from Google News RSS feeds.
    No API key needed. Free. Real-time.

    Returns list of raw headline dicts ready for classification.
    """
    headlines = []
    today = datetime.date.today().isoformat()

    for material, queries in RSS_QUERIES.items():
        for query in queries:
            try:
                # Google News RSS — free public endpoint
                url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en&gl=US&ceid=US:en"
                feed = feedparser.parse(url)

                for entry in feed.entries[:max_per_query]:
                    headlines.append({
                        "headline": entry.get("title", ""),
                        "source": entry.get("source", {}).get("title", "Google News"),
                        "url": entry.get("link", ""),
                        "date": entry.get("published", today)[:10],
                        "material": material,
                        "finbert_label": None,    # To be filled by FinBERT
                        "finbert_score": None,
                        "score": None,
                        "magnitude": None,
                        "classified_by": "pending",
                        "reasoning": None,
                    })

            except Exception as e:
                print(f"  [RSS] Failed to fetch '{query}': {e}")

    # Deduplicate by headline
    seen = set()
    unique = []
    for h in headlines:
        key = h["headline"].lower()[:60]
        if key not in seen:
            seen.add(key)
            unique.append(h)

    print(f"  [RSS] Fetched {len(unique)} unique headlines")
    return unique


# ─── LAYER 1: FINBERT CLASSIFICATION ──────────────────────────────────────────

def classify_with_finbert(headline: str) -> dict:
    """
    Calls HuggingFace FinBERT to classify a headline.
    Uses your HuggingFace credits — ~$0.0001 per call.

    Returns: {label, score, raw_scores}
    Falls back to simple keyword rules if HF token missing.
    """
    # Fallback if no HF token provided
    if not HF_TOKEN:
        return _keyword_fallback(headline)

    try:
        response = requests.post(
            FINBERT_URL,
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            json={"inputs": headline},
            timeout=10,
        )

        if response.status_code == 200:
            results = response.json()
            if isinstance(results, list) and results:
                items = results[0] if isinstance(results[0], list) else results
                # items = [{"label": "positive", "score": 0.87}, ...]
                top = max(items, key=lambda x: x["score"])
                label = top["label"].lower()
                confidence = top["score"]

                # Convert to signed score: positive = price rise signal
                # For procurement: price rise = buy urgency (positive score)
                signed = confidence if label == "positive" else -confidence if label == "negative" else 0.0

                return {
                    "label": label,
                    "score": round(signed, 3),
                    "confidence": round(confidence, 3),
                    "raw": {r["label"]: r["score"] for r in items},
                    "classified_by": "finbert",
                }

        print(f"  [FinBERT] Status {response.status_code} — using keyword fallback")
        return _keyword_fallback(headline)

    except Exception as e:
        print(f"  [FinBERT] Error: {e} — using keyword fallback")
        return _keyword_fallback(headline)


def _keyword_fallback(headline: str) -> dict:
    """
    Simple keyword-based sentiment when FinBERT is unavailable.
    Less accurate but works offline with no dependencies.
    """
    headline_lower = headline.lower()

    BULLISH = [
        "outage", "cut", "shortage", "surge", "spike", "disruption",
        "drought", "sanctions", "ban", "closure", "strike", "halt",
        "mandate", "regulation tightens", "capacity reduction",
    ]
    BEARISH = [
        "oversupply", "surplus", "drop", "fall", "decline", "weak",
        "record harvest", "eases", "low", "glut", "import surge",
    ]

    bull_count = sum(1 for w in BULLISH if w in headline_lower)
    bear_count = sum(1 for w in BEARISH if w in headline_lower)

    if bull_count > bear_count:
        score = min(0.65, 0.3 + bull_count * 0.15)
        label = "positive"
    elif bear_count > bull_count:
        score = -min(0.65, 0.3 + bear_count * 0.15)
        label = "negative"
    else:
        score = 0.0
        label = "neutral"

    return {
        "label": label,
        "score": round(score, 3),
        "confidence": round(abs(score), 3),
        "raw": {},
        "classified_by": "keyword_fallback",
    }


# ─── LAYER 2: CLAUDE EXPLANATION ──────────────────────────────────────────────

def explain_with_claude(headline: str, finbert_result: dict, material: str) -> str:
    """
    Calls Claude to explain WHY this headline matters for Damm's procurement.
    Only called for high-impact headlines (|score| > CLAUDE_THRESHOLD).

    This is the explainability layer the challenge requires.
    Cost: ~$0.01 per call — use sparingly, only for top signals.
    """
    client = anthropic.Anthropic()

    prompt = f"""You are a procurement analyst for Damm, a Catalan beer company.
Damm's key raw materials are: aluminium (cans), vPET/rPET (bottles), barley (brewing), energy/gas.

A news classifier flagged this headline as {finbert_result['label']} (confidence: {finbert_result['confidence']:.0%}):

Headline: "{headline}"
Primary material flagged: {material}

In exactly 2 sentences:
1. Explain the supply chain mechanism — WHY does this news affect {material} prices for Damm specifically?
2. State the likely price direction and time horizon (e.g. "prices likely up within 4-6 weeks").

Be specific. Mention actual supply chain links (e.g. Turkey exports, LME, EU regulation, smelting costs).
Do not repeat the headline. Do not hedge excessively."""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",   # Cheaper model — reasoning is short
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as e:
        return f"[Explanation unavailable: {e}]"


# ─── MAGNITUDE CLASSIFIER ─────────────────────────────────────────────────────

def _assign_magnitude(score: float, headline: str) -> str:
    """
    Assigns magnitude (high/medium/low) based on score and keywords.
    High-magnitude events get Claude explanation. Others just get FinBERT score.
    """
    HIGH_IMPACT_WORDS = [
        "record", "crisis", "ban", "sanctions", "halt", "outage",
        "collapse", "force majeure", "war", "earthquake", "explosion",
        "mandate", "anti-dumping",
    ]
    has_high_word = any(w in headline.lower() for w in HIGH_IMPACT_WORDS)
    abs_score = abs(score)

    if abs_score >= 0.65 or has_high_word:
        return "high"
    elif abs_score >= 0.35:
        return "medium"
    else:
        return "low"


# ─── MASTER CLASSIFIER ────────────────────────────────────────────────────────

def classify_headlines(
    headlines: list[dict],
    use_claude_for_top_n: int = 5,
) -> list[dict]:
    """
    Runs the full two-layer classification pipeline on a list of headlines.

    Step 1: Check cache — skip any headline already classified
    Step 2: Run FinBERT on uncached headlines (uses HF credits)
    Step 3: Run Claude on the top N high-magnitude headlines (uses Anthropic credits)
    Step 4: Save to cache

    use_claude_for_top_n: how many headlines to send to Claude for explanation
    """
    cache = _load_cache()
    results = []
    needs_claude = []

    print(f"\n[Classifier] Processing {len(headlines)} headlines...")

    for item in headlines:
        headline = item["headline"]
        cache_key = _headline_key(headline)

        # Step 1: Cache hit — reuse
        if cache_key in cache:
            results.append({**item, **cache[cache_key], "from_cache": True})
            continue

        # Step 2: FinBERT classification
        fb = classify_with_finbert(headline)
        magnitude = _assign_magnitude(fb["score"], headline)

        classified = {
            **item,
            "finbert_label": fb["label"],
            "finbert_score": fb["confidence"],
            "score": fb["score"],
            "magnitude": magnitude,
            "classified_by": fb["classified_by"],
            "reasoning": None,
            "from_cache": False,
        }

        # Queue for Claude if high magnitude
        if magnitude == "high" and abs(fb["score"]) >= CLAUDE_THRESHOLD:
            needs_claude.append((cache_key, classified))

        cache[cache_key] = {
            "finbert_label": classified["finbert_label"],
            "finbert_score": classified["finbert_score"],
            "score": classified["score"],
            "magnitude": classified["magnitude"],
            "classified_by": classified["classified_by"],
            "reasoning": None,
        }
        results.append(classified)

    # Step 3: Claude for top N high-impact headlines only
    # Sort by absolute score, take top N
    needs_claude.sort(key=lambda x: abs(x[1]["score"]), reverse=True)
    for cache_key, item in needs_claude[:use_claude_for_top_n]:
        print(f"  [Claude] Explaining: {item['headline'][:60]}...")
        reasoning = explain_with_claude(item["headline"], {
            "label": item["finbert_label"],
            "confidence": item["finbert_score"],
        }, item["material"])
        item["reasoning"] = reasoning
        item["classified_by"] = "finbert+claude"
        cache[cache_key]["reasoning"] = reasoning
        cache[cache_key]["classified_by"] = "finbert+claude"

    # Step 4: Save cache
    _save_cache(cache)

    print(f"  [Classifier] Done. {sum(1 for r in results if r.get('from_cache'))} from cache, "
          f"{sum(1 for r in results if r.get('classified_by') == 'finbert+claude')} explained by Claude.")

    return sorted(results, key=lambda x: abs(x.get("score", 0)), reverse=True)


# ─── COMPOSITE SIGNAL ─────────────────────────────────────────────────────────

def compute_composite_signal(
    news: list[dict],
    material: str,
    window_days: int = 21,
) -> dict:
    """
    Aggregates classified headlines into a single composite signal per material.

    The key insight from the challenge brief: individual headlines are noise,
    but MULTIPLE signals in the same direction within 3 weeks = structural shift.

    Returns:
      composite:    STRUCTURAL_SHIFT | TREND | NOISE
      direction:    bullish | bearish | neutral
      confidence:   HIGH | MEDIUM | LOW
      score:        -1.0 to +1.0
      signal_count: number of relevant headlines
      top_headlines: top 3 most impactful
    """
    cutoff = (datetime.date.today() - datetime.timedelta(days=window_days)).isoformat()

    # Filter to recent headlines for this material
    relevant = [
        n for n in news
        if n.get("material") in (material, "macro")
        and n.get("date", "") >= cutoff
        and n.get("score") is not None
    ]

    if not relevant:
        return {
            "composite": "NOISE",
            "direction": "neutral",
            "confidence": "LOW",
            "score": 0.0,
            "signal_count": 0,
            "top_headlines": [],
        }

    # Count signals by direction
    bullish = [n for n in relevant if n["score"] > 0.3]
    bearish = [n for n in relevant if n["score"] < -0.3]
    high_mag = [n for n in relevant if n.get("magnitude") == "high"]

    avg_score = sum(n["score"] for n in relevant) / len(relevant)

    # Classify composite signal
    # Rule: 3+ high-magnitude signals same direction = STRUCTURAL SHIFT
    if len(high_mag) >= 3:
        composite = "STRUCTURAL_SHIFT"
        confidence = "HIGH"
    elif len(bullish) >= 2 or len(bearish) >= 2:
        composite = "TREND"
        confidence = "MEDIUM"
    else:
        composite = "NOISE"
        confidence = "LOW"

    direction = "bullish" if avg_score > 0.1 else "bearish" if avg_score < -0.1 else "neutral"

    # Top 3 headlines by absolute impact
    top = sorted(relevant, key=lambda x: abs(x["score"]), reverse=True)[:3]

    return {
        "composite": composite,
        "direction": direction,
        "confidence": confidence,
        "score": round(avg_score, 3),
        "signal_count": len(relevant),
        "bullish_count": len(bullish),
        "bearish_count": len(bearish),
        "high_magnitude_count": len(high_mag),
        "top_headlines": top,
    }


if __name__ == "__main__":
    # Quick test with synthetic news
    from data_ingestion import generate_synthetic_news

    news = generate_synthetic_news(30)
    classified = classify_headlines(news, use_claude_for_top_n=0)  # 0 = no Claude calls in test

    print("\n=== Top 5 classified headlines ===")
    for item in classified[:5]:
        print(f"  [{item['score']:+.2f}] {item['headline'][:65]}")
        print(f"         Source: {item['source']} | Material: {item['material']} | Magnitude: {item['magnitude']}")

    print("\n=== Composite signals ===")
    for mat in ["aluminium", "barley", "vpet", "energy"]:
        sig = compute_composite_signal(classified, mat)
        print(f"  {mat:<12} {sig['composite']:<20} {sig['direction']:<10} score: {sig['score']:+.3f} ({sig['signal_count']} headlines)")
