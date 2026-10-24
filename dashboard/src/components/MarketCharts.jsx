import { Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import * as f from "../lib/format";
import { useTz } from "../lib/settings";

const MARK = { VOLUME_SPIKE: "V", PRICE_MOVE: "P", LARGE_TRADE: "L" };
const axis = { stroke: "var(--color-muted-foreground)", fontSize: 12, tickLine: false };
const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

// Alert marker: a labelled circle (letter + colour), so meaning never depends on colour alone.
function Marker({ cx, cy, payload }) {
  if (cx == null || cy == null) return null;
  const critical = payload.severity === "critical";
  return (
    <g>
      <circle cx={cx} cy={cy} r={9} fill={critical ? "var(--marker-critical)" : "var(--marker-warning)"} stroke="var(--color-card)" strokeWidth={2} />
      <text x={cx} y={cy + 4} textAnchor="middle" fontSize={10} fontWeight={700} fill="var(--marker-text)">{MARK[payload.type]}</text>
    </g>
  );
}

function TooltipBox({ active, payload, tz, quote }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div><span className="muted">Window</span><span className="num">{f.time(d.window_start, tz)}–{f.time(d.window_end, tz)}</span></div>
      <div><span className="muted">Close</span><span className="num">{f.price(d.close_price)}</span></div>
      <div><span className="muted">Change</span><span className="num">{f.pct(d.change_pct)}</span></div>
      <div><span className="muted">Volume</span><span className="num">{f.compact(d.quote_volume)} {quote}</span></div>
      <div><span className="muted">Trades</span><span className="num">{f.integer(d.trade_count)}</span></div>
    </div>
  );
}

/** Close price + alert markers, volume bars, and a table alternative. `indicators` oldest first. */
export default function MarketCharts({ indicators, alerts = [], symbol, height = 260 }) {
  const { tz } = useTz();
  const quote = f.quoteOf(symbol);
  const data = indicators.map((x) => ({
    ...x,
    t: Date.parse(x.window_start),
    close: f.toNum(x.close_price),
    vol: f.toNum(x.quote_volume),
  }));
  const byWindow = new Map(data.map((d) => [d.window_start, d]));
  // One marker per minute, the most telling one: critical first, then volume/price before large trade.
  // Replays can hold hundreds of alerts; the alert list next to the chart still shows every one.
  const rank = (a) => (a.severity === "critical" ? 2 : 0) + (a.type === "LARGE_TRADE" ? 0 : 1);
  const top = new Map();
  for (const a of alerts) {
    const d = byWindow.get(a.window_start);
    if (d && (!top.has(a.window_start) || rank(a) > rank(top.get(a.window_start).a))) top.set(a.window_start, { a, d });
  }
  const markers = [...top.values()];
  const tick = (t) => f.time(t, tz);
  const domain = ["dataMin", "dataMax"];

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 12, right: 12, bottom: 0, left: 0 }} syncId="market">
          <CartesianGrid stroke="var(--color-grid)" vertical={false} />
          <XAxis dataKey="t" type="number" scale="time" domain={domain} tickFormatter={tick} {...axis} minTickGap={40} />
          <YAxis domain={["auto", "auto"]} tickFormatter={(v) => f.price(v)} width={84} {...axis} />
          <Tooltip content={<TooltipBox tz={tz} quote={quote} />} />
          <Line type="monotone" dataKey="close" stroke="var(--color-chart-line)" strokeWidth={1.75} dot={false} isAnimationActive={!reduced} name="Close" />
          {markers.map(({ a, d }) => (
            <ReferenceDot key={a._id || `${a.type}-${a.event_time}`} x={d.t} y={d.close} shape={(p) => <Marker {...p} payload={a} />} ifOverflow="extendDomain" />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <ResponsiveContainer width="100%" height={110}>
        <BarChart data={data} margin={{ top: 4, right: 12, bottom: 0, left: 0 }} syncId="market">
          <XAxis dataKey="t" type="number" scale="time" domain={domain} tickFormatter={tick} {...axis} minTickGap={40} hide />
          <YAxis tickFormatter={(v) => f.compact(v)} width={84} {...axis} />
          <Tooltip content={<TooltipBox tz={tz} quote={quote} />} cursor={{ fill: "var(--tint-hover)" }} />
          <Bar dataKey="vol" fill="var(--color-chart-volume)" isAnimationActive={!reduced} name="Quote volume" />
        </BarChart>
      </ResponsiveContainer>
      <div className="legend">
        <span><i className="swatch" style={{ background: "var(--color-chart-line)" }} /> Close price ({quote})</span>
        <span><i className="swatch" style={{ background: "var(--color-chart-volume)", height: 10 }} /> Quote volume per minute ({quote})</span>
        <span className="legend-note">
          Alert markers, one per minute: <b>V</b> volume spike, <b>P</b> price move, <b>L</b> large trade; amber is a warning, red is critical.
        </span>
      </div>
      <details className="data-table">
        <summary>Show data table ({data.length} minutes, {f.tzLabel(tz)})</summary>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Window</th><th className="r">Open</th><th className="r">Close</th><th className="r">Min</th><th className="r">Max</th>
                <th className="r">Change</th><th className="r">Trades</th><th className="r">Volume ({quote})</th>
              </tr>
            </thead>
            <tbody>
              {[...data].reverse().map((d) => (
                <tr key={d.window_start}>
                  <td className="num">{f.time(d.window_start, tz)}</td>
                  <td className="r num">{f.price(d.open_price)}</td>
                  <td className="r num">{f.price(d.close_price)}</td>
                  <td className="r num">{f.price(d.min_price)}</td>
                  <td className="r num">{f.price(d.max_price)}</td>
                  <td className="r num">{f.pct(d.change_pct)}</td>
                  <td className="r num">{f.integer(d.trade_count)}</td>
                  <td className="r num">{f.integer(d.quote_volume)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
