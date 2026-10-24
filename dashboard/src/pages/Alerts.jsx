import { api, REFRESH_MS } from "../api";
import AlertList from "../components/AlertList";
import { Async, DateTimeField, Empty, LastUpdated, Notice, PageHead, Select, SymbolPicker } from "../components/ui";
import * as f from "../lib/format";
import { useParam } from "../lib/settings";
import { useApi } from "../lib/useApi";

const TYPES = [{ value: "", label: "All types" }, ...Object.entries(f.ALERT_TYPES).map(([value, t]) => ({ value, label: t.label }))];
const SEVERITIES = [{ value: "", label: "All" }, { value: "warning", label: "Warning" }, { value: "critical", label: "Critical" }];

export default function Alerts() {
  const [symbol, setSymbol] = useParam("symbol", "");
  const [type, setType] = useParam("type", "");
  const [severity, setSeverity] = useParam("severity", "");
  const [from, setFrom] = useParam("from", "");
  const [to, setTo] = useParam("to", "");
  const q = useApi((o) => api.alerts({ symbol, type, severity, from, to, limit: 200 }, o), [symbol, type, severity, from, to], { refreshMs: REFRESH_MS });
  const filtered = symbol || type || severity || from || to;

  return (
    <>
      <PageHead title="Alerts" description="Anomalies detected by Spark (collection alerts). Each one shows the measured value, the threshold it crossed and why.">
        <SymbolPicker value={symbol} onChange={setSymbol} allowAll />
        <Select label="Type" value={type} onChange={setType} options={TYPES} />
        <Select label="Severity" value={severity} onChange={setSeverity} options={SEVERITIES} />
        <DateTimeField label="From" value={from} onChange={setFrom} />
        <DateTimeField label="To" value={to} onChange={setTo} />
      </PageHead>
      <LastUpdated q={q} refreshMs={REFRESH_MS} />

      <Notice>
        Thresholds are <b>demo settings</b> chosen by the team, not market standards: volume spike ≥ 2.0× the 20-minute mean (after 20 minutes of warm-up),
        price move ≥ 0.5 % close-to-close, large trade ≥ 100,000 USDT. <b>Critical</b> means twice the threshold.
      </Notice>

      <section className="card" aria-label="Alert list">
        <Async
          q={q}
          height={300}
          empty={
            <Empty title={filtered ? "No alert matches these filters" : "No alerts yet"}>
              {filtered ? "Try removing a filter or widening the period." : "Alerts appear when a threshold is crossed."}
            </Empty>
          }
        >
          {(rows) => (
            <>
              <div className="card-head">
                <h2>{rows.length} alert{rows.length > 1 ? "s" : ""}</h2>
                <span className="hint">Newest first</span>
              </div>
              <AlertList alerts={rows} />
            </>
          )}
        </Async>
      </section>
    </>
  );
}
