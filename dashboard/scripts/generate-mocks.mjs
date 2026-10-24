// Generates the DEMO fixtures in src/mocks/fixtures/ (run: npm run mocks).
// Shapes follow docs/contracts.md (Spark output contracts) and docs/dashboard-api-needs.md.
// Values are synthetic but consistent with Ali's rules, so the screens look like real output.
// Output is deterministic (seeded) so the demo is reproducible.
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const OUT = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "mocks", "fixtures");

// Ali's demo defaults (docs/spark-operations.md)
const VOLUME_SPIKE_FACTOR = 2.0;
const LOOKBACK = 20;
const PRICE_MOVE_PCT = 0.5;
const LARGE_TRADE_QUOTE = 100000;

function rng(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const iso = (ms) => new Date(ms).toISOString().replace(".000Z", "Z");
const round = (x, d) => Number(x.toFixed(d));

function series({ symbol, start, minutes, basePrice, baseQty, runId, mode, seed, spikes = [], moves = [], largeTrades = [] }) {
  const r = rng(seed);
  const indicators = [];
  const alerts = [];
  let price = basePrice;
  const priceDp = basePrice > 10000 ? 2 : 2;
  for (let i = 0; i < minutes; i++) {
    const ws = start + i * 60000;
    const open = price;
    let drift = (r() - 0.5) * 0.0016;
    if (moves.includes(i)) drift = (r() > 0.5 ? 1 : -1) * (0.0055 + r() * 0.006);
    const close = open * (1 + drift);
    const hi = Math.max(open, close) * (1 + r() * 0.0006);
    const lo = Math.min(open, close) * (1 - r() * 0.0006);
    const spike = spikes.includes(i) ? 2.6 + r() * 2.4 : 1;
    const trades = Math.round((180 + r() * 380) * spike);
    const baseVol = baseQty * (0.6 + r() * 0.8) * spike;
    const avg = (open + close + hi + lo) / 4;
    const prev = indicators[indicators.length - 1];
    const ind = {
      _id: `${runId}:${symbol}:${iso(ws)}`,
      run_id: runId, mode, symbol,
      window_start: iso(ws), window_end: iso(ws + 60000),
      trade_count: trades,
      base_volume: round(baseVol, 6),
      quote_volume: round(baseVol * avg, 2),
      min_price: round(lo, priceDp), max_price: round(hi, priceDp), avg_price: round(avg, priceDp),
      open_price: round(open, priceDp), close_price: round(close, priceDp),
      change_pct: prev ? round((100 * (round(close, priceDp) - prev.close_price)) / prev.close_price, 4) : null,
      prev_window_start: prev ? prev.window_start : null,
      updated_at: iso(ws + 125000),
    };
    indicators.push(ind);

    // VOLUME_SPIKE: same rule as gold.window_alerts
    if (indicators.length > LOOKBACK) {
      const window = indicators.slice(-LOOKBACK - 1, -1);
      const baseline = window.reduce((s, x) => s + x.quote_volume, 0) / LOOKBACK;
      const ratio = ind.quote_volume / baseline;
      if (ratio >= VOLUME_SPIKE_FACTOR) {
        alerts.push({
          _id: `${runId}:VOLUME_SPIKE:${symbol}:${ind.window_start}`,
          run_id: runId, mode, symbol, type: "VOLUME_SPIKE",
          severity: ratio >= 2 * VOLUME_SPIKE_FACTOR ? "critical" : "warning",
          event_time: ind.window_end, window_start: ind.window_start,
          observed_value: round(ratio, 4), threshold: VOLUME_SPIKE_FACTOR, baseline: round(baseline, 2), unit: "ratio",
          reason: `Volume of ${ind.quote_volume.toFixed(0)} USDT in this minute is ${ratio.toFixed(1)}x the mean of the previous ${LOOKBACK} minutes (${baseline.toFixed(0)} USDT); threshold ${VOLUME_SPIKE_FACTOR.toFixed(1)}x`,
          ref_event_id: null, created_at: ind.updated_at,
        });
      }
    }
    // PRICE_MOVE
    if (ind.change_pct !== null && Math.abs(ind.change_pct) >= PRICE_MOVE_PCT) {
      alerts.push({
        _id: `${runId}:PRICE_MOVE:${symbol}:${ind.window_start}`,
        run_id: runId, mode, symbol, type: "PRICE_MOVE",
        severity: Math.abs(ind.change_pct) >= 2 * PRICE_MOVE_PCT ? "critical" : "warning",
        event_time: ind.window_end, window_start: ind.window_start,
        observed_value: ind.change_pct, threshold: PRICE_MOVE_PCT, baseline: prev.close_price, unit: "percent",
        reason: `Close moved ${ind.change_pct >= 0 ? "+" : ""}${ind.change_pct.toFixed(2)}% versus the previous window (${prev.close_price} to ${ind.close_price}); threshold ${PRICE_MOVE_PCT.toFixed(2)}%`,
        ref_event_id: null, created_at: ind.updated_at,
      });
    }
    // LARGE_TRADE
    if (largeTrades.includes(i)) {
      const qty = round((LARGE_TRADE_QUOTE * (1.05 + r() * 1.6)) / close, 5);
      const quote = qty * round(close, priceDp);
      const tradeId = 4100000000 + i * 997;
      const t = ws + Math.floor(r() * 59000);
      alerts.push({
        _id: `${runId}:LARGE_TRADE:${symbol}:binance:${symbol}:${tradeId}`,
        run_id: runId, mode, symbol, type: "LARGE_TRADE",
        severity: quote >= 2 * LARGE_TRADE_QUOTE ? "critical" : "warning",
        event_time: iso(t), window_start: ind.window_start,
        observed_value: round(quote, 2), threshold: LARGE_TRADE_QUOTE, baseline: null, unit: "USDT",
        reason: `Single trade of ${quote.toFixed(0)} USDT (${qty} at ${round(close, priceDp)}) reaches the ${LARGE_TRADE_QUOTE} threshold`,
        ref_event_id: `binance:${symbol}:${tradeId}`, created_at: iso(t + 2000),
      });
    }
    price = close;
  }
  return { indicators, alerts };
}

// Live demo period: 2026-10-24 07:00-11:00 UTC (240 minutes) per symbol.
const LIVE_START = Date.parse("2026-10-24T07:00:00Z");
const btc = series({ symbol: "BTCUSDT", start: LIVE_START, minutes: 240, basePrice: 67120, baseQty: 3.2, runId: "live", mode: "live", seed: 11, spikes: [64, 151, 222, 236], moves: [97, 230], largeTrades: [40, 118, 203, 233] });
const eth = series({ symbol: "ETHUSDT", start: LIVE_START, minutes: 240, basePrice: 2648, baseQty: 52, runId: "live", mode: "live", seed: 29, spikes: [88, 190, 231], moves: [140, 228], largeTrades: [75, 210] });

// Replay demo: what jobs/replay.py would write for --run-id replay-btc-demo.
const REPLAY_START = Date.parse("2026-07-01T00:00:00Z");
const replay = series({ symbol: "BTCUSDT", start: REPLAY_START, minutes: 180, basePrice: 61840, baseQty: 4.1, runId: "replay-btc-demo", mode: "replay", seed: 7, spikes: [33, 95, 160], moves: [58, 121], largeTrades: [12, 140] });

const byTimeDesc = (a, b) => b.event_time.localeCompare(a.event_time);

// Editorial demo items: titles are invented for the demo; scores mimic VADER compound values.
const headlines = [
  ["BTC", "Bitcoin holds above key support as ETF inflows continue", "positive", 0.62],
  ["BTC", "Analysts warn of thin weekend liquidity in bitcoin markets", "negative", -0.44],
  ["ETH", "Ethereum developers schedule next network upgrade call", "neutral", 0.03],
  ["BTC,ETH", "Crypto market steady ahead of US inflation data", "neutral", 0.0],
  ["ETH", "Ether staking deposits reach a new monthly high", "positive", 0.51],
  ["BTC", "Large bitcoin transfer to exchange sparks selling fears", "negative", -0.58],
  ["ETH", "DeFi lending volumes rebound on Ethereum", "positive", 0.47],
  ["BTC", "Miners report stable hash rate after difficulty adjustment", "neutral", 0.08],
  ["BTC,ETH", "Regulator clarifies rules for crypto custody providers", "positive", 0.36],
  ["ETH", "Gas fees spike briefly during NFT mint", "negative", -0.27],
  ["BTC", "Bitcoin volatility index falls to a three-week low", "positive", 0.29],
  ["BTC,ETH", "Exchange outage briefly halts withdrawals", "negative", -0.66],
  ["ETH", "Layer-2 networks process record daily transactions", "positive", 0.55],
  ["BTC", "Long-term holders keep accumulating, on-chain data shows", "positive", 0.41],
  ["BTC", "Funding rates turn neutral after weekend swings", "neutral", -0.02],
  ["ETH", "Ethereum foundation moves funds, community debates intent", "neutral", -0.04],
];
const sentiment = headlines.map(([assets, title, label, score], i) => {
  const t = LIVE_START + (i * 240 * 60000) / headlines.length + 7 * 60000;
  const isSocial = i % 4 === 3;
  const src = isSocial ? `reddit:demo${1000 + i}` : `rss:demo${String(i).padStart(4, "0")}`;
  const symbols = assets.split(",");
  return {
    _id: `sentiment:${src}`, event_id: `sentiment:${src}`, source_event_id: src,
    source_topic: isSocial ? "crypto-social" : "crypto-news", source: isSocial ? "reddit" : "rss",
    symbols, trade_symbols: symbols.map((s) => `${s}USDT`),
    label, score, model: "vader",
    event_time: iso(t), processed_at: iso(t + 4000), stored_at: iso(t + 9000),
    title, url: `https://example.com/demo/${i}`,
  };
}).reverse();

const runs = [{
  run_id: "replay-btc-demo", symbols: ["BTCUSDT"],
  start: replay.indicators[0].window_start, end: replay.indicators.at(-1).window_end,
  indicator_count: replay.indicators.length, alert_count: replay.alerts.length,
}];

mkdirSync(OUT, { recursive: true });
const write = (name, data) => writeFileSync(join(OUT, name), JSON.stringify(data) + "\n");
write("indicators.json", [...btc.indicators, ...eth.indicators]);
write("alerts.json", [...btc.alerts, ...eth.alerts].sort(byTimeDesc));
write("sentiment.json", sentiment);
write("replay-runs.json", runs);
write("replay-indicators.json", replay.indicators);
write("meta.json", { demo: true, generated_by: "scripts/generate-mocks.mjs", demo_end: btc.indicators.at(-1).window_end });
write("replay-alerts.json", replay.alerts.sort(byTimeDesc));
console.log(`indicators ${btc.indicators.length + eth.indicators.length}, alerts ${btc.alerts.length + eth.alerts.length}, sentiment ${sentiment.length}, replay ${replay.indicators.length}/${replay.alerts.length}`);
