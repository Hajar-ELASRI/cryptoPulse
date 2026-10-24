import { Link } from "react-router-dom";
import { api, REFRESH_MS, SYMBOLS } from "../api";
import AlertList from "../components/AlertList";
import MarketCharts from "../components/MarketCharts";
import { Async, Change, Empty, LastUpdated, Notice, PageHead, Stat, SymbolPicker } from "../components/ui";
import * as f from "../lib/format";
import { useParam, useTz } from "../lib/settings";
import { useApi } from "../lib/useApi";

export default function Live() {
  const { tz } = useTz();
  const [symbol, setSymbol] = useParam("symbol", SYMBOLS[0]);
  const live = useApi((o) => api.live({ symbol, limit: 60 }, o), [symbol], { refreshMs: REFRESH_MS });
  const alerts = useApi((o) => api.alerts({ symbol, limit: 50 }, o), [symbol], { refreshMs: REFRESH_MS });
  const quote = f.quoteOf(symbol);
  const base = f.baseOf(symbol);

  return (
    <>
      <PageHead title="Live market" description="Per-minute indicators computed by Spark from Binance trades (collection indicators, mode live).">
        <SymbolPicker value={symbol} onChange={setSymbol} />
      </PageHead>
      <LastUpdated q={live} refreshMs={REFRESH_MS} />

      <Async q={live} height={96} empty={<Empty title={`No live indicators for ${symbol} yet`}>Spark writes a window about 2 minutes after its minute ends. Check that spark-trades and spark-indicators are running.</Empty>}>
        {(rows) => {
          const last = rows[0];
          return (
            <div className="stats">
              <Stat label={`Last close (${quote})`} value={f.price(last.close_price)} sub={`Window ${f.time(last.window_start, tz)}–${f.time(last.window_end, tz)} ${f.tzLabel(tz)}`} />
              <Stat label="Change vs previous window" value={<Change value={last.change_pct} />} sub={last.prev_window_start ? `Close vs close of ${f.time(last.prev_window_start, tz)}` : "No previous window"} />
              <Stat label={`Volume this minute (${quote})`} value={f.compact(last.quote_volume)} sub={`${f.decimal(last.base_volume, 4)} ${base}`} />
              <Stat label="Trades this minute" value={f.integer(last.trade_count)} sub={`Avg price ${f.price(last.avg_price)}`} />
              <Stat label={`Min / max (${quote})`} value={<span className="stat-value-sm">{f.price(last.min_price)} / {f.price(last.max_price)}</span>} sub="Within this minute" />
            </div>
          );
        }}
      </Async>

      <div className="grid-2">
        <section className="card" aria-labelledby="chart-title">
          <div className="card-head">
            <h2 id="chart-title">{symbol} · last 60 minutes</h2>
            <span className="hint">One point per one-minute window, {f.tzLabel(tz)}</span>
          </div>
          <Async q={live} height={370} empty={<Empty />}>
            {(rows) => <MarketCharts indicators={[...rows].reverse()} alerts={alerts.data || []} symbol={symbol} />}
          </Async>
        </section>

        <section className="card" aria-labelledby="recent-alerts">
          <div className="card-head">
            <h2 id="recent-alerts">Latest alerts</h2>
            <Link to={`/alerts?symbol=${symbol}`} className="hint">See all</Link>
          </div>
          <Async q={alerts} height={200} empty={<Empty title="No alerts">No threshold crossed for {symbol} recently.</Empty>}>
            {(rows) => <AlertList alerts={rows.slice(0, 5)} compact />}
          </Async>
        </section>
      </div>

      <Notice>
        Change is measured on the <b>close</b> price against the previous window of the same symbol (Ali's contract). A live window is written once, after a
        1-minute watermark, so the newest minute appears with about 2 minutes of delay.
      </Notice>
    </>
  );
}
