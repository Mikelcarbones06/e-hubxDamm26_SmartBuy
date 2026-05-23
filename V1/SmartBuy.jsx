import { useState, useEffect, useRef } from "react";
import { AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

// ─── Design tokens ────────────────────────────────────────────────────────────
const C = {
  bg:      "#080b0f",
  s1:      "#0f1318",
  s2:      "#151a22",
  border:  "#1d2535",
  accent:  "#e8a020",
  teal:    "#2dd4bf",
  purple:  "#a78bfa",
  red:     "#f87171",
  green:   "#4ade80",
  blue:    "#60a5fa",
  text:    "#e2e8f0",
  muted:   "#64748b",
  muted2:  "#334155",
};

const ACTION_STYLE = {
  BUY:     { bg: "#4ade8018", border: "#4ade8044", color: "#4ade80", icon: "↑" },
  HEDGE:   { bg: "#60a5fa18", border: "#60a5fa44", color: "#60a5fa", icon: "⟳" },
  WAIT:    { bg: "#f8717118", border: "#f8717144", color: "#f87171", icon: "↓" },
  MONITOR: { bg: "#e8a02018", border: "#e8a02044", color: "#e8a020", icon: "◎" },
};

const MATERIAL_META = {
  aluminium: { label: "Aluminium",      emoji: "🔩", note: "Highest spend — cans" },
  vpet:      { label: "vPET",           emoji: "🧴", note: "Virgin PET bottles" },
  rpet:      { label: "rPET",           emoji: "♻️", note: "Recycled PET — EU mandate" },
  barley:    { label: "Malted Barley",  emoji: "🌾", note: "Core brewing ingredient" },
  energy:    { label: "Energy / Gas",   emoji: "⚡", note: "EU TTF natural gas" },
};

// ─── Mock data (used when backend is offline) ─────────────────────────────────
function buildMock() {
  const months = 36;
  const now = new Date();
  const makeChart = (start, vol, drift) => {
    let v = start;
    return Array.from({ length: months }, (_, i) => {
      const d = new Date(now);
      d.setMonth(d.getMonth() - (months - i));
      v *= (1 + drift + (Math.random() - 0.5) * vol);
      const ma30 = v * (1 + (Math.random() - 0.5) * 0.01);
      return { date: d.toISOString().slice(0, 7), value: +v.toFixed(1), ma30: +ma30.toFixed(1), bb_upper: +(ma30 * 1.04).toFixed(1), bb_lower: +(ma30 * 0.96).toFixed(1) };
    });
  };

  const makeRec = (name, action, score, pct, price, driversUp, driversDown, signals, horizon, hedgeH) => ({
    material_name: name, action, score, confidence: score > 75 ? "HIGH" : "MEDIUM",
    horizon, hedge_horizon: hedgeH,
    drivers_up: driversUp, drivers_down: driversDown, signals,
    forecast: { current_price: price, forecast_30d_pct: pct, forecast_7d_pct: pct / 4, r2: 0.68 },
    score_components: { price_trend: Math.round(score * 0.4), market_pressure: Math.round(score * 0.25), news_composite: Math.round(score * 0.2), historical: Math.round(score * 0.15) },
    anomalies: score > 65 ? [{ date: new Date().toISOString().slice(0, 10), z_score: -2.1, direction: "drop", value: price }] : [],
    analogues: [
      { date: "2023-03-15", price_at_time: price * 0.92, outcome_30d_pct: 5.2, outcome_direction: "up", pct30d_at_time: -4.1, z30_at_time: -1.8 },
      { date: "2022-10-08", price_at_time: price * 0.88, outcome_30d_pct: 3.1, outcome_direction: "up", pct30d_at_time: -3.2, z30_at_time: -1.4 },
      { date: "2023-11-20", price_at_time: price * 1.05, outcome_30d_pct: -2.3, outcome_direction: "down", pct30d_at_time: 2.1, z30_at_time: 1.2 },
    ],
    composite_signal: { composite: score > 70 ? "STRUCTURAL_SHIFT" : score > 50 ? "TREND" : "NOISE", direction: pct > 0 ? "bullish" : "bearish", confidence: "MEDIUM", signal_count: 12, bullish_count: 7, bearish_count: 5, high_magnitude_count: 3 },
    news_sentiment: { score: pct > 0 ? 0.31 : -0.28, count: 12, direction: pct > 0 ? "bullish" : "bearish" },
  });

  const recs = {
    aluminium: makeRec("Aluminium", "BUY", 78, 5.2, 2340, ["European smelter cuts due to gas prices", "LME inventory at 6-year low", "Speculative net-long positions rising"], ["China demand uncertainty"], ["Strong uptrend: +5.2% forecast 30 days", "Price 1.9σ below 30-day average — attractive entry", "STRUCTURAL SHIFT: 3 major supply events in 14 days", "Historical analogues: +5.2% avg in similar conditions"], "within 14 days (urgent — cover lead time)", null),
    vpet:      makeRec("vPET", "HEDGE", 61, 3.1, 835, ["Turkey capacity cut 8%", "PTA plant outage China"], ["Weak EU demand Q2", "Asian imports rising"], ["Mild uptrend forecast +3.1%", "Turkey supplier risk elevated", "News trend: bullish (7 vs 5 signals)"], "hedge within 21 days to secure current price", "hedge 60 days forward — moderate conviction"),
    rpet:      makeRec("rPET", "MONITOR", 45, 1.2, 948, ["EU 30% mandate from 2026 drives structural demand"], ["Virgin PET softening reduces premium", "Collection rate growth slowing"], ["Flat trend +1.2%", "Compliance deadline creates floor — cannot wait indefinitely", "News: neutral (0.08 score)"], "reassess in 5–7 days as signals develop", null),
    barley:    makeRec("Malted Barley", "WAIT", 28, -4.8, 228, [], ["Spain/France harvest upgraded +12%", "Global supply comfortable", "Wheat price falling — barley follows"], ["Strong downtrend: −4.8% forecast", "Price 1.6σ above 30-day average — expensive", "Historical analogues: −3.1% avg in similar conditions"], "wait 3–4 weeks — strong downtrend expected", null),
    energy:    makeRec("Energy / Gas", "MONITOR", 48, 0.8, 38, ["Winter storage drawdown risk", "Russia transit uncertainty"], ["TTF storage at 68% — above average", "Mild May forecast"], ["Flat EU gas price +0.8%", "Seasonal: summer = lower demand", "Geopolitical risk remains elevated"], "reassess in 5–7 days as signals develop", null),
  };

  const charts = {
    aluminium: makeChart(2340, 0.06, 0.003),
    vpet:      makeChart(835, 0.04, 0.002),
    rpet:      makeChart(948, 0.05, 0.003),
    barley:    makeChart(228, 0.08, -0.003),
    energy:    makeChart(38, 0.15, 0.001),
  };

  const news = [
    { headline: "European aluminium smelters cut output 9% amid persistently high gas prices", source: "Reuters", material: "aluminium", score: 0.78, magnitude: "high", date: new Date().toISOString().slice(0,10), reasoning: "Gas accounts for 40% of aluminium smelting costs. Capacity cuts tighten EU supply within 4-6 weeks, pushing LME prices higher." },
    { headline: "LME aluminium warehouse inventory falls to lowest since 2018", source: "Bloomberg", material: "aluminium", score: 0.71, magnitude: "high", date: new Date(Date.now()-86400000).toISOString().slice(0,10), reasoning: "Low inventories amplify any supply shock. For Damm's can sheet procurement, this signals tighter availability and higher spot prices within 2-3 weeks." },
    { headline: "Spain barley harvest forecast upgraded 12% on improved rainfall", source: "Expana", material: "barley", score: -0.65, magnitude: "high", date: new Date(Date.now()-172800000).toISOString().slice(0,10), reasoning: "Better Spanish harvest directly reduces Damm's procurement cost for local barley. Expect prices to soften 3-5% over the next 4 weeks as harvest data confirms." },
    { headline: "Turkey PET producer reduces export capacity by 8% following plant maintenance", source: "ICIS", material: "vpet", score: 0.62, magnitude: "high", date: new Date(Date.now()-259200000).toISOString().slice(0,10), reasoning: "Turkey is Europe's primary PET import source. A capacity reduction tightens spot availability, likely pushing EU vPET prices up 3-4% within 3 weeks." },
    { headline: "EU proposes mandatory 30% rPET content for all beverage bottles from 2026", source: "Fastmarkets", material: "rpet", score: 0.58, magnitude: "medium", date: new Date(Date.now()-432000000).toISOString().slice(0,10), reasoning: null },
    { headline: "Russian gas transit via Ukraine halted — EU TTF spikes 12%", source: "FT", material: "energy", score: -0.75, magnitude: "high", date: new Date(Date.now()-518400000).toISOString().slice(0,10), reasoning: "Gas price spikes directly increase aluminium smelting costs, likely transmitting to LME prices within 4-6 weeks. Also affects Damm production energy costs." },
  ];

  return { recs, charts, news };
}

const MOCK = buildMock();

// ─── API helpers ──────────────────────────────────────────────────────────────
const API = "http://localhost:8000/api";
async function apiFetch(path, opts = {}) {
  try {
    const r = await fetch(API + path, { ...opts, headers: { "Content-Type": "application/json" } });
    if (!r.ok) throw new Error(r.status);
    return await r.json();
  } catch { return null; }
}

const fmt = (n, d = 1) => n != null ? (+n).toFixed(d) : "—";
const fmtPct = n => n != null ? `${n > 0 ? "+" : ""}${fmt(n)}%` : "—";
const fmtPrice = (n, unit = "") => n != null ? `${(+n).toLocaleString("en", { minimumFractionDigits: 0, maximumFractionDigits: 0 })} ${unit}` : "—";

// ─── Components ───────────────────────────────────────────────────────────────
function Card({ children, style }) {
  return <div style={{ background: C.s1, border: `1px solid ${C.border}`, borderRadius: 10, padding: "18px 20px", ...style }}>{children}</div>;
}
function Label({ children, color, style }) {
  return <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: color || C.muted, marginBottom: 8, ...style }}>{children}</div>;
}

function ActionBadge({ action, score, confidence, size = "normal" }) {
  const s = ACTION_STYLE[action] || ACTION_STYLE.MONITOR;
  const big = size === "large";
  return (
    <div style={{ display: "inline-flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <div style={{ background: s.bg, border: `1px solid ${s.border}`, borderRadius: 10, padding: big ? "14px 28px" : "8px 16px", textAlign: "center" }}>
        <div style={{ fontSize: big ? 32 : 14, color: s.color, fontWeight: 800, letterSpacing: "0.06em" }}>
          {s.icon} {action}
        </div>
        {big && <div style={{ fontSize: 11, color: C.muted, marginTop: 4 }}>{confidence} confidence</div>}
      </div>
      {big && (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <svg width={80} height={80} viewBox="0 0 80 80">
            <circle cx={40} cy={40} r={32} fill="none" stroke={C.border} strokeWidth={7} />
            <circle cx={40} cy={40} r={32} fill="none" stroke={s.color} strokeWidth={7}
              strokeDasharray={`${score / 100 * 201} 201`} strokeLinecap="round"
              transform="rotate(-90 40 40)" />
            <text x={40} y={44} textAnchor="middle" fill={s.color} fontSize={18} fontWeight={700} fontFamily="monospace">{score}</text>
          </svg>
          <div style={{ fontSize: 11, color: C.muted }}>/ 100</div>
        </div>
      )}
    </div>
  );
}

function ScoreBar({ label, value, max, color }) {
  const pct = (value / max) * 100;
  const col = pct >= 66 ? C.green : pct >= 33 ? C.accent : C.red;
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: C.muted }}>{label}</span>
        <span style={{ fontSize: 11, color: col, fontFamily: "monospace" }}>{value}/{max}</span>
      </div>
      <div style={{ height: 4, background: C.border, borderRadius: 2 }}>
        <div style={{ height: "100%", width: `${pct}%`, background: col, borderRadius: 2, transition: "width 0.6s ease" }} />
      </div>
    </div>
  );
}

function PriceChart({ data, color = C.accent }) {
  const tick = { fill: C.muted, fontSize: 10 };
  return (
    <ResponsiveContainer width="100%" height={180}>
      <AreaChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -10 }}>
        <defs>
          <linearGradient id="cg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity={0.25} />
            <stop offset="95%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={C.border} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="date" tick={tick} tickLine={false} interval={11} />
        <YAxis tick={tick} tickLine={false} axisLine={false} domain={["auto", "auto"]} />
        <Tooltip contentStyle={{ background: C.s2, border: `1px solid ${C.border}`, borderRadius: 8, fontSize: 11 }} labelStyle={{ color: C.muted }} />
        <Area type="monotone" dataKey="bb_upper" fill="none" stroke={`${color}22`} strokeDasharray="3 3" dot={false} name="Upper" />
        <Area type="monotone" dataKey="bb_lower" fill="none" stroke={`${color}22`} strokeDasharray="3 3" dot={false} name="Lower" />
        <Area type="monotone" dataKey="ma30" fill="none" stroke={`${color}55`} strokeDasharray="4 4" dot={false} name="MA30" />
        <Area type="monotone" dataKey="value" fill="url(#cg)" stroke={color} strokeWidth={2} dot={false} name="Price" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function NewsItem({ item }) {
  const col = item.score > 0.3 ? C.green : item.score < -0.3 ? C.red : C.muted;
  return (
    <div style={{ padding: "10px 12px", background: C.s2, borderRadius: 8, borderLeft: `3px solid ${col}`, marginBottom: 8 }}>
      <div style={{ fontSize: 12, color: C.text, lineHeight: 1.45, marginBottom: 4 }}>{item.headline}</div>
      {item.reasoning && (
        <div style={{ fontSize: 11, color: C.muted, lineHeight: 1.4, marginBottom: 4, fontStyle: "italic" }}>
          {item.reasoning}
        </div>
      )}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontSize: 10, color: C.muted }}>{item.source}</span>
        <span style={{ fontSize: 10, color: C.muted }}>{item.date}</span>
        <span style={{ fontSize: 10, color: col, fontWeight: 600 }}>{item.score > 0 ? "+" : ""}{(item.score * 100).toFixed(0)} • {item.magnitude}</span>
        <span style={{ fontSize: 10, background: C.s1, color: C.muted, padding: "1px 6px", borderRadius: 4 }}>{item.material}</span>
      </div>
    </div>
  );
}

function Analogues({ analogues }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {analogues.map((a, i) => {
        const col = a.outcome_direction === "up" ? C.green : C.red;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 14px", background: C.s2, borderRadius: 8 }}>
            <div style={{ fontSize: 22, color: col }}>{a.outcome_direction === "up" ? "↑" : "↓"}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, color: C.muted }}>{a.date}</div>
              <div style={{ fontSize: 11, color: C.muted2, marginTop: 2 }}>
                Price: {fmt(a.price_at_time)} · Δ30d: {fmtPct(a.pct30d_at_time)} · z: {fmt(a.z30_at_time, 1)}σ
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: col, fontFamily: "monospace" }}>{fmtPct(a.outcome_30d_pct)}</div>
              <div style={{ fontSize: 10, color: C.muted }}>30-day outcome</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ChatPanel({ recs }) {
  const [msgs, setMsgs] = useState([
    { role: "assistant", content: "Hello. I'm SmartBuy. Ask me anything about aluminium, PET, barley or energy procurement timing." }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const SUGGESTIONS = [
    "Which material should I prioritise buying this week?",
    "What if gas prices spike 20%?",
    "Is rPET compliance at risk?",
    "Compare aluminium vs barley urgency",
  ];

  const send = async (text) => {
    const q = text || input.trim();
    if (!q) return;
    setInput("");
    setMsgs(m => [...m, { role: "user", content: q }]);
    setLoading(true);

    const history = msgs.slice(1).map(m => ({ role: m.role, content: m.content }));
    const res = await apiFetch("/chat", { method: "POST", body: JSON.stringify({ question: q, history }) });

    const FALLBACKS = {
      "prioriti": "Based on current scores: Aluminium (78/100, BUY) is the most urgent — tightest supply conditions with a 28-day lead time. Barley should be delayed (28/100, WAIT) as harvest forecasts are improving. vPET warrants partial hedging.",
      "gas": "A 20% gas spike would directly increase aluminium smelting costs by ~8-12 EUR/tonne, likely pushing LME prices up 5-8% within 4-6 weeks. For Damm, this would flip the aluminium recommendation from BUY to HEDGE IMMEDIATELY. rPET production costs would also rise ~3-4%.",
      "rpet": "rPET compliance is currently MONITOR (45/100). The EU 25% mandate is in force now, rising to 30% in 2026. Based on current consumption rates, you need to secure rPET supply within the next 30 days to maintain compliance. The current stock provides limited buffer.",
      "compare": "Aluminium: BUY (78/100) — 28-day lead time, tightest conditions, highest spend. Barley: WAIT (28/100) — harvest improving, prices falling. Act on aluminium first.",
    };
    const fallback = Object.entries(FALLBACKS).find(([k]) => q.toLowerCase().includes(k));
    const answer = res?.answer ?? (fallback ? fallback[1] : "I can help with that. Could you provide more context about which material or timeframe you're asking about?");

    setMsgs(m => [...m, { role: "assistant", content: answer }]);
    setLoading(false);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: 440 }}>
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8, paddingBottom: 8 }}>
        {msgs.map((m, i) => (
          <div key={i} style={{
            alignSelf: m.role === "user" ? "flex-end" : "flex-start",
            maxWidth: "88%",
            background: m.role === "user" ? `${C.accent}18` : C.s2,
            border: `1px solid ${m.role === "user" ? C.accent + "44" : C.border}`,
            borderRadius: 10, padding: "10px 14px", fontSize: 13, color: C.text, lineHeight: 1.55,
          }}>
            {m.content}
          </div>
        ))}
        {loading && <div style={{ color: C.muted, fontSize: 13, padding: "4px 12px" }}>Thinking…</div>}
        <div ref={bottomRef} />
      </div>
      <div style={{ marginTop: 6, display: "flex", gap: 6, flexWrap: "wrap" }}>
        {SUGGESTIONS.map(s => (
          <button key={s} onClick={() => send(s)} style={{
            background: C.s2, border: `1px solid ${C.border}`, borderRadius: 6,
            color: C.muted, fontSize: 11, padding: "4px 10px", cursor: "pointer",
          }}>{s}</button>
        ))}
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && send()}
          placeholder="Ask about timing, hedging, scenarios…"
          style={{ flex: 1, background: C.s2, border: `1px solid ${C.border}`, borderRadius: 8, color: C.text, fontSize: 13, padding: "10px 14px", outline: "none" }} />
        <button onClick={() => send()} style={{ background: C.accent, color: "#000", border: "none", borderRadius: 8, padding: "10px 18px", fontWeight: 700, fontSize: 13, cursor: "pointer" }}>
          Send
        </button>
      </div>
    </div>
  );
}

function NarrativeSection({ matId, rec }) {
  const [text, setText] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    const res = await apiFetch(`/narrative/${matId}`);
    const FALLBACK = {
      aluminium: `**Aluminium market: BUY signal — score 78/100**\n\nEuropean smelters have cut output by ~9% due to elevated natural gas costs, while LME warehouse inventories have fallen to their lowest since 2018. Speculative net-long positions on aluminium futures are rising, suggesting institutional investors anticipate further price appreciation. Current spot price is trading 1.9σ below its 30-day average, presenting an attractive entry window before these supply constraints feed through.\n\n**30-day outlook:** +5.2% price increase expected as smelter output cuts materialise in physical availability. Key risk: a sharp drop in gas prices could reverse smelter profitability and ease cuts. Historical analogues from March 2023 and October 2022 — both periods with similar inventory and smelter conditions — showed +5.2% and +3.1% respectively.\n\n**Recommendation: BUY within 14 days.** With a 28-day lead time, you need to order now to cover demand at current prices. Suggest covering 60-70% of next 45-day requirement, retaining 30% flexibility.`,
      barley: `**Barley market: WAIT — score 28/100**\n\nThe 2024 Iberian harvest is tracking 12% above initial forecasts following improved spring rainfall across Spain and southern France. Global wheat markets — a key barley price correlate — are also softening, with Australian export supply comfortable. Current barley price is elevated vs its 30-day moving average, suggesting the market hasn't fully priced in the improving harvest.\n\n**30-day outlook:** −4.8% decline expected as harvest data confirms supply improvement. Historical analogues from similar pre-harvest periods show average declines of 3-5%.\n\n**Recommendation: WAIT 3-4 weeks.** Allow harvest data to be confirmed and prices to correct before purchasing. Every week of delay at current trend saves approximately 1-2% on procurement cost.`,
    };
    setText(res?.narrative ?? FALLBACK[matId] ?? `[Narrative not available for ${matId}]`);
    setLoading(false);
  };

  return (
    <div>
      {!text && !loading && (
        <button onClick={load} style={{
          background: `${C.accent}18`, border: `1px solid ${C.accent}44`,
          borderRadius: 8, color: C.accent, padding: "10px 18px", fontSize: 13, cursor: "pointer", fontWeight: 600,
        }}>
          Generate AI Briefing
        </button>
      )}
      {loading && <div style={{ color: C.muted, fontSize: 13 }}>Generating briefing…</div>}
      {text && <div style={{ fontSize: 13, color: C.text, lineHeight: 1.75, whiteSpace: "pre-wrap" }}>{text}</div>}
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function SmartBuy() {
  const [recs, setRecs] = useState(null);
  const [charts, setCharts] = useState(null);
  const [news, setNews] = useState([]);
  const [selected, setSelected] = useState("aluminium");
  const [tab, setTab] = useState("overview");
  const [dammLoaded, setDammLoaded] = useState(false);

  useEffect(() => {
    // Try live backend, fall back to mock
    apiFetch("/dashboard").then(dash => {
      if (dash) {
        setRecs(dash.materials);
        setNews(dash.top_news || []);
        setDammLoaded(dash.damm_barley_loaded);
        // Load chart data for selected material
        apiFetch(`/material/${selected}`).then(mat => {
          if (mat) setCharts(prev => ({ ...prev, [selected]: mat.chart_data }));
        });
      } else {
        setRecs(MOCK.recs);
        setCharts(MOCK.charts);
        setNews(MOCK.news);
      }
    });
  }, []);

  useEffect(() => {
    // Load chart data when material changes
    if (!charts?.[selected]) {
      apiFetch(`/material/${selected}`).then(mat => {
        if (mat) setCharts(prev => ({ ...prev, [selected]: mat.chart_data }));
        else if (MOCK.charts[selected]) setCharts(prev => ({ ...prev, [selected]: MOCK.charts[selected] }));
      });
    }
  }, [selected]);

  if (!recs) return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", color: C.muted, fontFamily: "monospace" }}>
      Loading SmartBuy…
    </div>
  );

  const rec = recs[selected] || {};
  const chartData = charts?.[selected] || [];
  const COLORS = { aluminium: C.accent, vpet: C.teal, rpet: "#2dd4bf", barley: "#86efac", energy: C.purple };
  const matColor = COLORS[selected] || C.accent;

  return (
    <div style={{ background: C.bg, minHeight: "100vh", color: C.text, fontFamily: "'IBM Plex Sans', system-ui, sans-serif" }}>

      {/* Header */}
      <div style={{ borderBottom: `1px solid ${C.border}`, padding: "14px 28px", display: "flex", alignItems: "center", gap: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 30, height: 30, background: C.accent, borderRadius: 7, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, color: "#000", fontSize: 14 }}>S</div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, letterSpacing: "-0.02em" }}>SmartBuy</div>
            <div style={{ fontSize: 10, color: C.muted }}>Damm Procurement Intelligence</div>
          </div>
        </div>
        {dammLoaded && (
          <div style={{ background: "#4ade8018", border: "1px solid #4ade8044", borderRadius: 6, padding: "3px 10px", fontSize: 11, color: C.green }}>
            ✓ Damm barley data loaded
          </div>
        )}
        <div style={{ flex: 1 }} />
        {["overview", "detail", "chat", "sources"].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            background: tab === t ? C.s2 : "transparent",
            border: `1px solid ${tab === t ? C.border : "transparent"}`,
            borderRadius: 6, color: tab === t ? C.text : C.muted,
            padding: "6px 14px", fontSize: 12, cursor: "pointer", textTransform: "capitalize",
          }}>{t}</button>
        ))}
      </div>

      {/* Material selector */}
      <div style={{ padding: "14px 28px 0", display: "flex", gap: 8, flexWrap: "wrap" }}>
        {Object.entries(MATERIAL_META).map(([id, meta]) => {
          const r = recs[id];
          if (!r) return null;
          const s = ACTION_STYLE[r.action] || ACTION_STYLE.MONITOR;
          const active = selected === id;
          return (
            <button key={id} onClick={() => setSelected(id)} style={{
              background: active ? `${s.color}18` : C.s1,
              border: `1px solid ${active ? s.color + "66" : C.border}`,
              borderRadius: 9, padding: "10px 16px", cursor: "pointer", textAlign: "left", minWidth: 130,
            }}>
              <div style={{ fontSize: 16, marginBottom: 2 }}>{meta.emoji}</div>
              <div style={{ fontSize: 12, fontWeight: 600, color: active ? C.text : C.muted }}>{meta.label}</div>
              <div style={{ fontSize: 11, color: s.color, fontWeight: 700, marginTop: 2 }}>{r.action} · {r.score}</div>
            </button>
          );
        })}
      </div>

      <div style={{ padding: "16px 28px", display: "flex", flexDirection: "column", gap: 16 }}>

        {/* ── OVERVIEW ── */}
        {tab === "overview" && (
          <>
            {/* Top row */}
            <div style={{ display: "grid", gridTemplateColumns: "auto 1fr 1fr", gap: 14, alignItems: "start" }}>

              <Card style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14, padding: "24px 28px" }}>
                <ActionBadge action={rec.action} score={rec.score} confidence={rec.confidence} size="large" />
                {rec.hedge_horizon && (
                  <div style={{ background: `${C.blue}15`, border: `1px solid ${C.blue}33`, borderRadius: 8, padding: "8px 14px", fontSize: 12, color: C.blue, textAlign: "center" }}>
                    {rec.hedge_horizon}
                  </div>
                )}
                <div style={{ background: C.s2, borderRadius: 8, padding: "10px 14px", width: "100%", fontSize: 12 }}>
                  <div style={{ color: C.muted, marginBottom: 4, fontSize: 11 }}>Suggested horizon</div>
                  <div style={{ color: C.text, lineHeight: 1.4 }}>{rec.horizon}</div>
                </div>
              </Card>

              <Card>
                <Label>Price forecast — {MATERIAL_META[selected]?.label}</Label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  {[
                    { label: "Current price", value: fmtPrice(rec.forecast?.current_price) },
                    { label: "Trend", value: rec.forecast?.trend?.toUpperCase(), color: rec.forecast?.trend === "up" ? C.green : rec.forecast?.trend === "down" ? C.red : C.muted },
                    { label: "+7 days", value: fmtPct(rec.forecast?.forecast_7d_pct), color: (rec.forecast?.forecast_7d_pct || 0) > 0 ? C.green : C.red },
                    { label: "+30 days", value: fmtPct(rec.forecast?.forecast_30d_pct), color: (rec.forecast?.forecast_30d_pct || 0) > 0 ? C.green : C.red },
                  ].map(({ label, value, color }) => (
                    <div key={label}>
                      <div style={{ fontSize: 10, color: C.muted, marginBottom: 3 }}>{label}</div>
                      <div style={{ fontSize: 18, fontWeight: 600, color: color || C.text, fontFamily: "monospace" }}>{value}</div>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 16 }}>
                  <ScoreBar label="Price trend" value={rec.score_components?.price_trend || 0} max={40} />
                  <ScoreBar label="Market pressure" value={rec.score_components?.market_pressure || 0} max={25} />
                  <ScoreBar label="News composite" value={rec.score_components?.news_composite || 0} max={20} />
                  <ScoreBar label="Historical analogues" value={rec.score_components?.historical || 0} max={15} />
                </div>
              </Card>

              <Card>
                <Label>Drivers</Label>
                {rec.drivers_up?.length > 0 && (
                  <>
                    <div style={{ fontSize: 11, color: C.green, fontWeight: 600, marginBottom: 6 }}>↑ Pushing price UP</div>
                    {rec.drivers_up.map((d, i) => (
                      <div key={i} style={{ fontSize: 12, color: C.muted, marginBottom: 6, paddingLeft: 10, borderLeft: `2px solid ${C.green}` }}>{d}</div>
                    ))}
                  </>
                )}
                {rec.drivers_down?.length > 0 && (
                  <>
                    <div style={{ fontSize: 11, color: C.red, fontWeight: 600, margin: "10px 0 6px" }}>↓ Pushing price DOWN</div>
                    {rec.drivers_down.map((d, i) => (
                      <div key={i} style={{ fontSize: 12, color: C.muted, marginBottom: 6, paddingLeft: 10, borderLeft: `2px solid ${C.red}` }}>{d}</div>
                    ))}
                  </>
                )}
                <div style={{ marginTop: 12, padding: "8px 12px", background: C.s2, borderRadius: 8 }}>
                  <div style={{ fontSize: 10, color: C.muted, marginBottom: 4 }}>News composite</div>
                  <div style={{ fontSize: 12, color: rec.composite_signal?.direction === "bullish" ? C.green : rec.composite_signal?.direction === "bearish" ? C.red : C.muted, fontWeight: 600 }}>
                    {rec.composite_signal?.composite} — {rec.composite_signal?.direction}
                  </div>
                  <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>
                    {rec.composite_signal?.signal_count} headlines · {rec.composite_signal?.high_magnitude_count} high-impact
                  </div>
                </div>
              </Card>
            </div>

            {/* Chart + signals */}
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14 }}>
              <Card>
                <Label>{MATERIAL_META[selected]?.label} price — 36 months</Label>
                <PriceChart data={chartData} color={matColor} />
                <div style={{ fontSize: 10, color: C.muted, marginTop: 6 }}>Dashed = MA30 · Bands = ±2σ Bollinger</div>
              </Card>
              <Card>
                <Label>Evidence signals</Label>
                <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                  {(rec.signals || []).map((s, i) => (
                    <div key={i} style={{ fontSize: 12, color: C.muted, lineHeight: 1.5, paddingLeft: 10, borderLeft: `2px solid ${C.border}` }}>{s}</div>
                  ))}
                </div>
              </Card>
            </div>

            {/* AI briefing */}
            <Card>
              <Label>AI market briefing</Label>
              <NarrativeSection matId={selected} rec={rec} />
            </Card>
          </>
        )}

        {/* ── DETAIL ── */}
        {tab === "detail" && (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <Card>
                <Label>Historical analogues</Label>
                <div style={{ fontSize: 12, color: C.muted, marginBottom: 12, lineHeight: 1.5 }}>
                  Most similar 30-period market windows and what happened next
                </div>
                <Analogues analogues={rec.anomalies?.length > 0
                  ? [...(rec.analogues || [])].slice(0, 3)
                  : (rec.analogues || [])} />
              </Card>
              <Card>
                <Label>Recent news — {MATERIAL_META[selected]?.label}</Label>
                <div style={{ maxHeight: 340, overflowY: "auto" }}>
                  {news.filter(n => n.material === selected || n.material === "macro" || n.material === "energy")
                    .slice(0, 6).map((n, i) => <NewsItem key={i} item={n} />)}
                </div>
              </Card>
            </div>
            <Card>
              <Label>All materials — score overview</Label>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 }}>
                {Object.entries(recs).map(([id, r]) => {
                  const s = ACTION_STYLE[r.action] || ACTION_STYLE.MONITOR;
                  const m = MATERIAL_META[id];
                  return (
                    <div key={id} onClick={() => { setSelected(id); setTab("overview"); }}
                      style={{ background: C.s2, borderRadius: 8, padding: "12px 14px", cursor: "pointer", border: `1px solid ${C.border}`, textAlign: "center" }}>
                      <div style={{ fontSize: 20 }}>{m?.emoji}</div>
                      <div style={{ fontSize: 11, color: C.muted, margin: "4px 0" }}>{m?.label}</div>
                      <div style={{ fontSize: 22, fontWeight: 700, color: s.color, fontFamily: "monospace" }}>{r.score}</div>
                      <div style={{ fontSize: 11, color: s.color, fontWeight: 600 }}>{r.action}</div>
                      <div style={{ fontSize: 10, color: C.muted, marginTop: 4 }}>{fmtPct(r.forecast_30d_pct)}</div>
                    </div>
                  );
                })}
              </div>
            </Card>
          </>
        )}

        {/* ── CHAT ── */}
        {tab === "chat" && (
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14 }}>
            <Card>
              <Label>Procurement assistant</Label>
              <ChatPanel recs={recs} />
            </Card>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <Card>
                <Label>Quick reference</Label>
                {Object.entries(recs).map(([id, r]) => {
                  const s = ACTION_STYLE[r.action] || ACTION_STYLE.MONITOR;
                  return (
                    <div key={id} style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                      <span style={{ fontSize: 12, color: C.muted }}>{MATERIAL_META[id]?.emoji} {MATERIAL_META[id]?.label}</span>
                      <span style={{ fontSize: 12, color: s.color, fontWeight: 700 }}>{r.action} · {r.score}</span>
                    </div>
                  );
                })}
              </Card>
              <Card>
                <Label>Top news signal</Label>
                {news.slice(0, 3).map((n, i) => <NewsItem key={i} item={n} />)}
              </Card>
            </div>
          </div>
        )}

        {/* ── SOURCES ── */}
        {tab === "sources" && (
          <Card>
            <Label>Documented data sources</Label>
            <div style={{ fontSize: 12, color: C.muted, marginBottom: 16 }}>
              All sources documented as required by the challenge brief. Origin, frequency, reliability, and influence on recommendation.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              {Object.entries(get_mock_sources()).map(([id, s]) => (
                <div key={id} style={{ background: C.s2, borderRadius: 8, padding: "12px 14px", borderLeft: `3px solid ${s.type === "internal" ? C.green : s.type === "partner_api" ? C.teal : s.type === "ml_model_api" ? C.purple : C.blue}` }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: C.text, marginBottom: 4 }}>{s.name}</div>
                  <div style={{ fontSize: 11, color: C.muted, marginBottom: 4 }}>
                    <span style={{ color: C.muted2 }}>Origin:</span> {s.origin}
                  </div>
                  <div style={{ fontSize: 11, color: C.muted, marginBottom: 4 }}>
                    <span style={{ color: C.muted2 }}>Frequency:</span> {s.frequency} · <span style={{ color: C.muted2 }}>Reliability:</span> {s.reliability?.split(" ")[0]}
                  </div>
                  <div style={{ fontSize: 11, color: C.muted, lineHeight: 1.4 }}>{s.influence}</div>
                </div>
              ))}
            </div>
          </Card>
        )}

      </div>
    </div>
  );
}

function get_mock_sources() {
  return {
    "damm_barley":       { name: "Damm Barley Dataset", origin: "Damm internal", type: "internal", frequency: "Daily", reliability: "HIGH", influence: "Direct price input for barley buy score" },
    "cala_structured":   { name: "Cala.ai Structured Data", origin: "Cala.ai partner", type: "partner_api", frequency: "On demand", reliability: "HIGH", influence: "Verified price feed for all materials" },
    "fred_barley":       { name: "IMF Barley Price (FRED)", origin: "IMF via US Federal Reserve", type: "public_api", frequency: "Monthly", reliability: "HIGH", influence: "Barley baseline price and trend" },
    "fred_aluminium":    { name: "IMF Aluminium Price (FRED)", origin: "IMF via FRED", type: "public_api", frequency: "Monthly", reliability: "HIGH", influence: "Aluminium baseline — highest spend" },
    "fred_oil_brent":    { name: "Brent Crude (FRED)", origin: "IMF via FRED", type: "public_api", frequency: "Monthly", reliability: "HIGH", influence: "Upstream driver for PET and aluminium" },
    "fred_nat_gas":      { name: "EU Natural Gas (FRED)", origin: "World Bank via FRED", type: "public_api", frequency: "Monthly", reliability: "HIGH", influence: "Key driver for aluminium smelting cost" },
    "google_news_rss":   { name: "Google News RSS", origin: "Google (Reuters, Bloomberg, ICIS...)", type: "public_rss", frequency: "Real-time", reliability: "MEDIUM", influence: "News sentiment input for all materials" },
    "cot_reports":       { name: "CFTC COT Report", origin: "US CFTC regulatory filing", type: "public_report", frequency: "Weekly", reliability: "HIGH", influence: "Speculative positioning — advanced signal" },
    "hf_finbert":        { name: "FinBERT (HuggingFace)", origin: "ProsusAI/finbert on HF Hub", type: "ml_model_api", frequency: "Per headline", reliability: "MEDIUM-HIGH", influence: "First-pass sentiment classification (uses HF credits)" },
    "eurostat_imports":  { name: "Eurostat COMEXT", origin: "European Commission", type: "public_api", frequency: "Monthly", reliability: "HIGH", influence: "EU PET import volumes from Turkey/Asia" },
  };
}
