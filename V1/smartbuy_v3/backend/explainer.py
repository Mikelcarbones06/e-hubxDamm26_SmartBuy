"""
SmartBuy — AI Explainer
========================
Uses Claude to generate:
  1. Full market narrative for a material
  2. Answers to free-form procurement questions
  3. Scenario analysis ("what if oil spikes 15%?")
"""

import json
import anthropic

client = anthropic.Anthropic()

SYSTEM = """You are SmartBuy, a procurement intelligence analyst for Damm,
a Catalan beer company (Estrella Damm). Damm buys aluminium (cans),
vPET and rPET (bottles), barley (brewing), and energy (production).

Your job: help the procurement team decide when to BUY, WAIT, HEDGE or MONITOR.

Rules:
- Be direct. Max 3 short paragraphs unless asked for more.
- Ground every claim in the data provided.
- Mention specific supply chain links (e.g. Turkish PET, LME aluminium, EU TTF gas).
- Aluminium is Damm's highest-spend category — treat it with priority.
- For rPET: compliance with EU mandates is non-negotiable — flag if at risk.
- Always mention the suggested horizon (how many days/weeks).
- Respond in the same language as the user's question.
"""


def generate_narrative(rec_dict: dict, news_top: list[dict]) -> str:
    """Generates a 3-paragraph market briefing for a material."""
    prompt = f"""Generate a procurement briefing for {rec_dict['material_name']}.

Recommendation data:
{json.dumps({
    'action': rec_dict['action'],
    'score': rec_dict['score'],
    'confidence': rec_dict['confidence'],
    'horizon': rec_dict['horizon'],
    'hedge_horizon': rec_dict.get('hedge_horizon'),
    'drivers_up': rec_dict['drivers_up'],
    'drivers_down': rec_dict['drivers_down'],
    'forecast_30d_pct': rec_dict['forecast']['forecast_30d_pct'],
    'current_price': rec_dict['forecast']['current_price'],
    'composite_signal': rec_dict['composite_signal']['composite'],
    'news_direction': rec_dict['composite_signal']['direction'],
}, indent=2)}

Top news signals:
{json.dumps([{'headline': n['headline'], 'score': n['score'], 'reasoning': n.get('reasoning')} for n in news_top[:4]], indent=2)}

Historical analogues:
{json.dumps(rec_dict['analogues'][:2], indent=2)}

Write 3 paragraphs:
1. Current market situation (what's happening and why)
2. Price outlook for 30 days with key risks and opportunities
3. Specific recommendation with horizon and justification

Under 220 words total. Start with the most important insight."""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        return f"[Narrative unavailable: {e}]"


def answer_question(question: str, context: dict, history: list[dict] = None) -> str:
    """Multi-turn procurement Q&A."""
    context_str = json.dumps({
        k: {
            "action": v.get("action"),
            "score": v.get("score"),
            "horizon": v.get("horizon"),
            "drivers_up": v.get("drivers_up", [])[:2],
            "drivers_down": v.get("drivers_down", [])[:2],
            "forecast_30d_pct": v.get("forecast", {}).get("forecast_30d_pct"),
        }
        for k, v in context.items() if isinstance(v, dict) and "action" in v
    }, indent=2)

    system = SYSTEM + f"\n\nCurrent recommendations:\n{context_str}"
    messages = (history or []) + [{"role": "user", "content": question}]

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=system,
            messages=messages,
        )
        return msg.content[0].text.strip()
    except Exception as e:
        return f"[Error: {e}]"


def analyse_scenario(scenario: str, material_id: str, rec_dict: dict) -> str:
    """What-if scenario analysis."""
    prompt = f"""Current situation for {rec_dict['material_name']}:
- Action: {rec_dict['action']} (score: {rec_dict['score']}/100)
- Horizon: {rec_dict['horizon']}
- Forecast: {rec_dict['forecast']['forecast_30d_pct']:+.1f}% over 30 days

Scenario to analyse: "{scenario}"

In under 150 words:
1. How does this scenario change the price outlook?
2. Does the recommendation change? If so, to what?
3. What specific risk or opportunity does this create for Damm?"""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        return f"[Error: {e}]"
