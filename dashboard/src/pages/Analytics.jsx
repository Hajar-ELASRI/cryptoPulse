import { useMemo } from "react";
import { api, defaultPeriod, SYMBOLS } from "../api";
import MarketCharts from "../components/MarketCharts";
import { Async, Change, DateTimeField, Empty, LastUpdated, Notice, PageHead, Stat, SymbolPicker } from "../components/ui";
import * as f from "../lib/format";
import { useParam, useTz } from "../lib/settings";
import { useApi } from "../lib/useApi";

function Summary({ s, symbol }) {
  const quote = f.quoteOf(symbol);
  const ac = s.alert_counts || {};
  const se = s.sentiment;
  return (
    <div className="stats">
      <Stat label="Change over the period" value={<Change value={s.change_pct} />} sub={`${f.price(s.open_price)} → ${f.price(s.close_price)} ${quote}`} />
      <Stat label={`Range (${quote})`} value={<span className="stat-value-sm">{f.price(s.min_price)} – {f.price(s.max_price)}</span>} sub="Lowest and highest trade" />
      <Stat label={`Total volume (${quote})`} value={f.compact(s.quote_volume)} sub={`${f.integer(s.trade_count)} trades`} />
      <Stat label="Alerts" value={f.integer((ac.VOLUME_SPIKE || 0) + (ac.PRICE_MOVE || 0) + (ac.LARGE_TRADE || 0))} sub={`${ac.VOLUME_SPIKE || 0} volume · ${ac.PRICE_MOVE || 0} price · ${ac.LARGE_TRADE || 0} large trade`} />
      {se && (
        <Stat
          label="Sentiment (observed)"
          value={se.count ? f.decimal(se.avg_score, 2) : "—"}
          sub={se.count ? `avg score of ${se.count} items · ${se.positive} positive · ${se.neutral} neutral · ${se.negative} negative` : "No scored items in period"}
        />
      )}
    </div>
  );
}

export default function Analytics() {
  const { tz } = useTz();
  const def = useMemo(defaultPeriod, []);
  const [symbol, setSymbol] = useParam("symbol", SYMBOLS[0]);
  const [from, setFrom] = useParam("from", def.from);
  const [to, setTo] = useParam("to", def.to);
  const valid = from && to && from < to;
  const q = useApi((o) => api.analytics({ symbol, from, to }, o), [symbol, from, to], { enabled: !!valid });
  const alerts = useApi((o) => api.alerts({ symbol, from, to, limit: 500 }, o), [symbol, from, to], { enabled: !!valid });

  return (
    <>
      <PageHead title="Analytics" description="Indicators of a symbol over a chosen period, with the alerts raised in it.">
        <SymbolPicker value={symbol} onChange={setSymbol} />
        <DateTimeField label="From" value={from} onChange={setFrom} />
        <DateTimeField label="To" value={to} onChange={setTo} />
      </PageHead>

      {!valid ? (
        <div className="card" role="alert"><Empty title="Choose a valid period">“From” must be before “To”.</Empty></div>
      ) : (
        <>
          <LastUpdated q={q} />
          <Async q={q} height={96} isEmpty={(d) => !d.indicators.length} empty={null}>
            {(d) =>
              d.summary ? <Summary s={d.summary} symbol={symbol} /> : <Notice>{d.indicators.length} one-minute windows from Spark in this period. Hover the chart or open its data table for each minute; the API does not compute period totals.</Notice>
            }
          </Async>
          <section className="card" aria-labelledby="an-chart">
            <div className="card-head">
              <h2 id="an-chart">{symbol} · {f.dateTime(from, tz)} → {f.dateTime(to, tz)} {f.tzLabel(tz)}</h2>
            </div>
            <Async q={q} height={370} isEmpty={(d) => !d.indicators.length} empty={<Empty title="No indicators in this period">Pick a period when the pipeline was running.</Empty>}>
              {(d) => <MarketCharts indicators={d.indicators} alerts={alerts.data || []} symbol={symbol} />}
            </Async>
          </section>
        </>
      )}
    </>
  );
}
