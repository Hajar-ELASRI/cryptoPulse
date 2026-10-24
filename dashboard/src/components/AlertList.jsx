import * as f from "../lib/format";
import { useTz } from "../lib/settings";
import { Severity } from "./ui";

/** Each alert explains itself: what, when, observed value vs threshold, baseline, Spark's reason. */
export default function AlertList({ alerts, compact = false }) {
  const { tz } = useTz();
  return (
    <ul className="alert-list plain-list">
      {alerts.map((a) => {
        const type = f.ALERT_TYPES[a.type] || { label: a.type, rule: "" };
        return (
          <li key={a._id || `${a.run_id}-${a.type}-${a.symbol}-${a.event_time}`} className={`alert ${a.severity === "critical" ? "critical" : ""} ${compact ? "compact" : ""}`}>
            <div className="alert-meta">
              <span className="num">{f.dateTime(a.event_time, tz)} {f.tzLabel(tz)}</span>
              <span><b>{a.symbol}</b></span>
              <Severity value={a.severity} />
            </div>
            <div>
              <div className="alert-type">
                {type.label}
                {a.mode === "replay" && <span className="badge badge-neutral">replay · {a.run_id}</span>}
              </div>
              <p className="alert-reason">{a.reason}</p>
              {!compact && (
                <div className="alert-figures">
                  <span>Observed <b>{f.alertValue(a.observed_value, a.unit)}</b></span>
                  <span>Threshold <b>{a.type === "PRICE_MOVE" ? `±${f.decimal(a.threshold, 2)} %` : f.alertValue(a.threshold, a.unit)}</b></span>
                  {a.baseline != null && (
                    <span>
                      Baseline <b>{a.type === "PRICE_MOVE" ? f.price(a.baseline) : `${f.integer(a.baseline)} ${f.quoteOf(a.symbol)}`}</b>
                      {a.type === "VOLUME_SPIKE" ? " (mean of previous 20 min)" : a.type === "PRICE_MOVE" ? " (previous close)" : ""}
                    </span>
                  )}
                  {a.window_start && a.type !== "LARGE_TRADE" && (
                    <span>Window <b>{f.time(a.window_start, tz)}–{f.time(a.event_time, tz)}</b></span>
                  )}
                  {a.ref_event_id && <span>Trade <b>{a.ref_event_id}</b></span>}
                  <span title={type.rule}>Rule: {type.rule}</span>
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
