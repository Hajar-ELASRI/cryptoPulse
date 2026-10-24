// Single entry point for data. Pages call these functions and never know whether the
// data comes from Mossab's API or from the demo fixtures. Routes follow docs/api.md
// (Mossab's contract); adjust here only when the real API changes.
import { request, asList, API_URL } from "./http";
import demoMeta from "../mocks/fixtures/meta.json";

// docs/api.md: limit is at most 500; a period is complete when a page has fewer rows.
const PAGE = 500;
const MAX_PAGES = 20; // 10,000 one-minute windows, about a week

async function allPages(fetchPage) {
  const pages = [];
  for (let page = 0; page < MAX_PAGES; page++) {
    const body = await fetchPage(page);
    pages.push(body);
    if (body.done) break;
  }
  return pages;
}

export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== "false";
export const REFRESH_MS = Number(import.meta.env.VITE_REFRESH_MS) || 30000;
export const SYMBOLS = (import.meta.env.VITE_SYMBOLS || "BTCUSDT,ETHUSDT").split(",").map((s) => s.trim().toUpperCase());
export { API_URL };

const real = {
  // /actuator/health is outside the API's CORS mapping (/api/**), so the smallest live read
  // serves as the check: it answers 503 DATA_UNAVAILABLE when MongoDB is down.
  health: (o) => request("/api/live", { limit: 1 }, o).then(() => ({ status: "UP" })),
  live: (p, o) => request("/api/live", p, o).then(asList),
  alerts: (p, o) => request("/api/alerts", p, o).then(asList),
  sentiment: (p, o) => request("/api/sentiment", p, o).then(asList),
  // The API returns no summary: the page shows Spark's windows only, nothing is recomputed here.
  analytics: async (p, o) => {
    const pages = await allPages(async (page) => {
      const b = await request("/api/analytics", { ...p, limit: PAGE, page }, o);
      const indicators = asList(b.indicators);
      return { indicators, done: indicators.length < PAGE };
    });
    return { indicators: pages.flatMap((b) => b.indicators), summary: null };
  },
  replayRuns: (o) => request("/api/replay/runs", null, o).then(asList),
  replay: async (runId, p, o) => {
    const pages = await allPages(async (page) => {
      const b = await request(`/api/replay/${encodeURIComponent(runId)}`, { ...p, limit: PAGE, page }, o);
      const indicators = asList(b.indicators);
      const alerts = asList(b.alerts);
      return { indicators, alerts, done: indicators.length < PAGE && alerts.length < PAGE };
    });
    return { run_id: runId, indicators: pages.flatMap((b) => b.indicators), alerts: pages.flatMap((b) => b.alerts) };
  },
};

// Fixtures are loaded only in demo mode, so they never ship in an API build.
const loadMock = () => import("../mocks/server");
const mock = new Proxy({}, { get: (_, name) => async (...args) => (await loadMock())[name](...args) });
const src = USE_MOCKS ? mock : real;

export const api = {
  health: (o) => src.health(o),
  /** Latest minute indicators of a symbol, newest first. */
  live: ({ symbol, limit = 60 }, o) => src.live({ symbol, limit }, o),
  /** Alerts, newest first. Filters: symbol, type, severity, from, to, limit, run_id. */
  alerts: (params, o) => src.alerts(params, o),
  /** Sentiment items (with source title/url when the API provides them), newest first. */
  sentiment: (params, o) => src.sentiment(params, o),
  /** { indicators (oldest first), summary | null } for a symbol and period. */
  analytics: (params, o) => src.analytics(params, o),
  replayRuns: (o) => src.replayRuns(o),
  /** { run_id, indicators, alerts } of one replay run. */
  replay: (runId, params, o) => src.replay(runId, params, o),
};

/** Default analytics period: the last 4 hours (of the demo data when mocks are on). */
export function defaultPeriod() {
  const end = USE_MOCKS ? Date.parse(demoMeta.demo_end) : Date.now();
  return { from: new Date(end - 4 * 3600e3).toISOString(), to: new Date(end).toISOString() };
}
