// DEMO ONLY: stands in for Mossab's API until it exists. It filters the fixtures the way the
// API is expected to (docs/dashboard-api-needs.md). Anything computed here (the analytics
// summary) is the server's job in the real system; the pages never compute it themselves.
import indicators from "./fixtures/indicators.json";
import alerts from "./fixtures/alerts.json";
import sentiment from "./fixtures/sentiment.json";
import replayRuns from "./fixtures/replay-runs.json";
import replayIndicators from "./fixtures/replay-indicators.json";
import replayAlerts from "./fixtures/replay-alerts.json";

const delay = (signal) =>
  new Promise((resolve, reject) => {
    const t = setTimeout(resolve, 250 + Math.random() * 250);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });

const inRange = (t, from, to) => (!from || t >= iso(from)) && (!to || t < iso(to));
const iso = (s) => new Date(s).toISOString().replace(".000Z", "Z");
const byStart = (a, b) => a.window_start.localeCompare(b.window_start);

export async function health(o) {
  await delay(o?.signal);
  return { status: "UP", mode: "demo" };
}

export async function live({ symbol, limit }, o) {
  await delay(o?.signal);
  return indicators
    .filter((x) => x.symbol === symbol)
    .sort((a, b) => byStart(b, a))
    .slice(0, limit);
}

export async function alertsList({ symbol, type, severity, from, to, limit = 100, run_id } = {}, o) {
  await delay(o?.signal);
  const source = run_id && run_id !== "live" ? replayAlerts.filter((a) => a.run_id === run_id) : alerts;
  return source
    .filter((a) => (!symbol || a.symbol === symbol) && (!type || a.type === type) && (!severity || a.severity === severity))
    .filter((a) => inRange(a.event_time, from, to))
    .slice(0, limit);
}
export { alertsList as alerts };

export async function sentimentList({ symbol, label, from, to, limit = 50 } = {}, o) {
  await delay(o?.signal);
  return sentiment
    .filter((s) => (!symbol || s.trade_symbols.includes(symbol)) && (!label || s.label === label))
    .filter((s) => inRange(s.event_time, from, to))
    .slice(0, limit);
}
export { sentimentList as sentiment };

export async function analytics({ symbol, from, to }, o) {
  await delay(o?.signal);
  const rows = indicators.filter((x) => x.symbol === symbol && inRange(x.window_start, from, to)).sort(byStart);
  if (!rows.length) return { symbol, from, to, indicators: [], summary: null };
  const al = alerts.filter((a) => a.symbol === symbol && inRange(a.event_time, from, to));
  const se = sentiment.filter((s) => s.trade_symbols.includes(symbol) && inRange(s.event_time, from, to));
  const first = rows[0];
  const last = rows[rows.length - 1];
  const count = (arr, k, v) => arr.filter((x) => x[k] === v).length;
  return {
    symbol, from, to, indicators: rows,
    summary: {
      trade_count: rows.reduce((s, x) => s + x.trade_count, 0),
      quote_volume: rows.reduce((s, x) => s + x.quote_volume, 0),
      open_price: first.open_price,
      close_price: last.close_price,
      min_price: Math.min(...rows.map((x) => x.min_price)),
      max_price: Math.max(...rows.map((x) => x.max_price)),
      change_pct: (100 * (last.close_price - first.open_price)) / first.open_price,
      alert_counts: { VOLUME_SPIKE: count(al, "type", "VOLUME_SPIKE"), PRICE_MOVE: count(al, "type", "PRICE_MOVE"), LARGE_TRADE: count(al, "type", "LARGE_TRADE") },
      sentiment: se.length
        ? { count: se.length, avg_score: se.reduce((s, x) => s + x.score, 0) / se.length, positive: count(se, "label", "positive"), neutral: count(se, "label", "neutral"), negative: count(se, "label", "negative") }
        : { count: 0, avg_score: null, positive: 0, neutral: 0, negative: 0 },
    },
  };
}

export async function replayRunsList(o) {
  await delay(o?.signal);
  return replayRuns;
}
export { replayRunsList as replayRuns };

export async function replay(runId, { symbol } = {}, o) {
  await delay(o?.signal);
  return {
    run_id: runId,
    indicators: replayIndicators.filter((x) => x.run_id === runId && (!symbol || x.symbol === symbol)).sort(byStart),
    alerts: replayAlerts.filter((a) => a.run_id === runId && (!symbol || a.symbol === symbol)),
  };
}
