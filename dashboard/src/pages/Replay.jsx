import { api } from "../api";
import AlertList from "../components/AlertList";
import MarketCharts from "../components/MarketCharts";
import { Async, Empty, Notice, PageHead, SymbolPicker } from "../components/ui";
import * as f from "../lib/format";
import { useParam, useTz } from "../lib/settings";
import { useApi } from "../lib/useApi";

const REPLAY_CMD = `docker compose --profile spark run --rm --no-deps spark-trades /opt/spark/bin/spark-submit \\
  --master 'local[2]' --conf spark.sql.shuffle.partitions=4 \\
  /opt/cryptopulse/cryptopulse_spark/jobs/replay.py \\
  --run-id replay-btc-demo --symbols BTCUSDT --start 2026-07-01T00:00:00Z --end 2026-07-01T06:00:00Z`;

export default function Replay() {
  const { tz } = useTz();
  const runs = useApi((o) => api.replayRuns(o), []);
  const [runId, setRunId] = useParam("run", "");
  const [symbol, setSymbol] = useParam("symbol", "");
  const selected = runs.data?.find((r) => r.run_id === runId);
  const runSymbol = symbol || selected?.symbols?.[0] || "";
  const q = useApi((o) => api.replay(runId, { symbol: runSymbol }, o), [runId, runSymbol], { enabled: !!selected });

  return (
    <>
      <PageHead title="Replay" description="Results of re-processing a historical period (trades_history) with the same Spark rules as live. Replay data never mixes with live data." />

      <section className="card" aria-labelledby="runs-title">
        <div className="card-head">
          <h2 id="runs-title">Replay runs</h2>
          <span className="hint">Choose a run</span>
        </div>
        <Async
          q={runs}
          height={90}
          empty={
            <Empty title="No replay run yet">
              Launch one with Ali's Spark job (docs/spark-operations.md):
              <code className="cmd">{REPLAY_CMD}</code>
            </Empty>
          }
        >
          {(list) => (
            <div className="runs">
              {list.map((r) => (
                <button key={r.run_id} type="button" className="run" aria-pressed={r.run_id === runId} onClick={() => { setRunId(r.run_id); setSymbol(""); }}>
                  <span className="run-id">{r.run_id}</span>
                  <span className="muted text-sm">
                    {f.dateTime(r.start, tz)} → {f.dateTime(r.end, tz)} {f.tzLabel(tz)}
                  </span>
                  <span className="text-sm">
                    {(r.symbols || []).join(", ")} · {f.integer(r.indicator_count)} windows · {f.integer(r.alert_count)} alerts
                  </span>
                </button>
              ))}
            </div>
          )}
        </Async>
      </section>

      {selected && (
        <>
          {selected.symbols?.length > 1 && <SymbolPicker value={runSymbol} onChange={setSymbol} />}
          <Notice>
            Run <b className="num">{selected.run_id}</b> covers {f.dateTime(selected.start, tz)} → {f.dateTime(selected.end, tz)} {f.tzLabel(tz)}. Running the same
            command again rewrites exactly the same results, so this replay is reproducible.
          </Notice>
          <div className="grid-2">
            <section className="card" aria-labelledby="rp-chart">
              <div className="card-head"><h2 id="rp-chart">{runSymbol} · replayed indicators</h2></div>
              <Async q={q} height={370} isEmpty={(d) => !d.indicators.length} empty={<Empty title="This run has no indicators for this symbol" />}>
                {(d) => <MarketCharts indicators={d.indicators} alerts={d.alerts} symbol={runSymbol} />}
              </Async>
            </section>
            <section className="card" aria-labelledby="rp-alerts">
              <div className="card-head"><h2 id="rp-alerts">Alerts in this replay</h2></div>
              <Async q={q} height={200} isEmpty={(d) => !d.alerts.length} empty={<Empty title="No alerts in this run" />}>
                {(d) => <AlertList alerts={d.alerts} compact />}
              </Async>
            </section>
          </div>
        </>
      )}
    </>
  );
}
