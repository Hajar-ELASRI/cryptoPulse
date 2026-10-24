// Display formatting only (no business calculation). Decimals may arrive as numbers or strings.

export const toNum = (v) => (v === null || v === undefined || v === "" ? null : Number(v));

const nf = (opts) => new Intl.NumberFormat("en-US", opts);
const DASH = "—";

export function price(v) {
  const n = toNum(v);
  if (n === null || Number.isNaN(n)) return DASH;
  const digits = Math.abs(n) >= 1000 ? 2 : Math.abs(n) >= 1 ? 2 : 6;
  return nf({ minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);
}

export function compact(v) {
  const n = toNum(v);
  if (n === null || Number.isNaN(n)) return DASH;
  return nf({ notation: "compact", maximumFractionDigits: 2 }).format(n);
}

export function integer(v) {
  const n = toNum(v);
  return n === null || Number.isNaN(n) ? DASH : nf({ maximumFractionDigits: 0 }).format(n);
}

export function decimal(v, digits = 4) {
  const n = toNum(v);
  return n === null || Number.isNaN(n) ? DASH : nf({ maximumFractionDigits: digits }).format(n);
}

// Rounded to what is displayed, so a tiny change never shows as "−0.00 %".
const shown = (n, digits) => Number(n.toFixed(digits));

export function pct(v, digits = 2) {
  const raw = toNum(v);
  if (raw === null || Number.isNaN(raw)) return DASH;
  const n = shown(raw, digits);
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${nf({ minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Math.abs(n))} %`;
}

export const direction = (v, digits = 2) => {
  const n = toNum(v);
  if (n === null || Number.isNaN(n)) return "flat";
  const r = shown(n, digits);
  return r === 0 ? "flat" : r > 0 ? "up" : "down";
};

/** Quote currency of a Binance pair, e.g. BTCUSDT -> USDT. */
export const quoteOf = (symbol = "") => (symbol.match(/(USDT|USDC|FDUSD|BTC|ETH|BNB)$/) || [])[1] || "";
export const baseOf = (symbol = "") => symbol.slice(0, symbol.length - quoteOf(symbol).length) || symbol;

/** Format an alert figure according to its `unit` (ratio, percent, currency). */
export function alertValue(v, unit) {
  const n = toNum(v);
  if (n === null) return DASH;
  if (unit === "ratio") return `${decimal(n, 2)}×`;
  if (unit === "percent") return pct(n);
  return `${integer(n)} ${unit || ""}`.trim();
}

// ---- Time: tz is "UTC" or "local"; the label always says which one is shown. ----
const LOCAL_TZ = Intl.DateTimeFormat().resolvedOptions().timeZone;

export const tzLabel = (tz) => (tz === "UTC" ? "UTC" : LOCAL_TZ);

function fmt(value, tz, opts) {
  if (!value) return DASH;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return DASH;
  return new Intl.DateTimeFormat("en-GB", { ...opts, hourCycle: "h23", timeZone: tz === "UTC" ? "UTC" : undefined }).format(d);
}

export const time = (v, tz) => fmt(v, tz, { hour: "2-digit", minute: "2-digit" });
export const timeSec = (v, tz) => fmt(v, tz, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
export const dateTime = (v, tz) => fmt(v, tz, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

/** ISO string -> value for <input type="datetime-local"> in the chosen zone. */
export function toInput(isoStr, tz) {
  if (!isoStr) return "";
  const d = new Date(isoStr);
  const shifted = tz === "UTC" ? d : new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return shifted.toISOString().slice(0, 16);
}

/** <input type="datetime-local"> value in the chosen zone -> ISO UTC string. */
export function fromInput(value, tz) {
  if (!value) return "";
  return tz === "UTC" ? new Date(`${value}:00Z`).toISOString() : new Date(value).toISOString();
}

export const ALERT_TYPES = {
  VOLUME_SPIKE: { label: "Volume spike", rule: "Minute quote volume ÷ mean of the previous 20 minutes ≥ threshold" },
  PRICE_MOVE: { label: "Price move", rule: "|Close change vs previous window| ≥ threshold (skipped after gaps > 5 min)" },
  LARGE_TRADE: { label: "Large trade", rule: "One trade's quote volume ≥ threshold" },
};
