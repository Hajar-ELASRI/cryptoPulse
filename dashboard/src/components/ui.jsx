import { useEffect, useState } from "react";
import { SYMBOLS, USE_MOCKS } from "../api";
import * as f from "../lib/format";
import { useTz } from "../lib/settings";
import { AlertOctagon, AlertTriangle, ArrowDown, ArrowUp, Flask, Inbox, Info, Minus, Refresh } from "./Icons";

export function PageHead({ title, description, children }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {children && <div className="controls">{children}</div>}
    </div>
  );
}

export function Segmented({ label, options, value, onChange }) {
  return (
    <div className="field">
      <span id={`seg-${label}`}>{label}</span>
      <div className="segmented" role="group" aria-labelledby={`seg-${label}`}>
        {options.map((o) => {
          const v = typeof o === "string" ? o : o.value;
          return (
            <button key={v} type="button" aria-pressed={value === v} onClick={() => onChange(v)}>
              {typeof o === "string" ? o : o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function SymbolPicker({ value, onChange, allowAll = false }) {
  const options = [...(allowAll ? [{ value: "", label: "All" }] : []), ...SYMBOLS.map((s) => ({ value: s, label: f.baseOf(s) }))];
  return <Segmented label="Symbol" options={options} value={value} onChange={onChange} />;
}

export function Select({ label, value, onChange, options }) {
  return (
    <label className="field">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}

export function DateTimeField({ label, value, onChange }) {
  const { tz } = useTz();
  return (
    <label className="field">
      {label} ({f.tzLabel(tz)})
      <input type="datetime-local" value={f.toInput(value, tz)} onChange={(e) => onChange(f.fromInput(e.target.value, tz))} />
    </label>
  );
}

export function Change({ value, digits = 2 }) {
  const dir = f.direction(value, digits);
  const Icon = dir === "up" ? ArrowUp : dir === "down" ? ArrowDown : Minus;
  return (
    <span className={`num ${dir === "flat" ? "muted" : dir}`} style={{ display: "inline-flex", alignItems: "center", gap: 2 }}>
      <Icon size={14} />
      {f.pct(value, digits)}
    </span>
  );
}

export function Stat({ label, value, sub }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export function Severity({ value }) {
  const critical = value === "critical";
  const Icon = critical ? AlertOctagon : AlertTriangle;
  return (
    <span className={`badge ${critical ? "badge-critical" : "badge-warning"}`}>
      <Icon size={12} />
      {critical ? "Critical" : "Warning"}
    </span>
  );
}

export function SentimentLabel({ value }) {
  const Icon = value === "positive" ? ArrowUp : value === "negative" ? ArrowDown : Minus;
  return (
    <span className={`badge badge-${value || "neutral"}`}>
      <Icon size={12} />
      {value ? value[0].toUpperCase() + value.slice(1) : "Unknown"}
    </span>
  );
}

export function DemoBadge() {
  if (!USE_MOCKS) return null;
  return (
    <span className="badge badge-demo" title="Synthetic demo data, not market data. Set VITE_USE_MOCKS=false to use the API.">
      <Flask size={12} /> DEMO DATA
    </span>
  );
}

export function Notice({ children, demo = false }) {
  return (
    <div className={`notice ${demo ? "notice-demo" : ""}`}>
      {demo ? <Flask /> : <Info />}
      <div>{children}</div>
    </div>
  );
}

export function Skeleton({ height = 240 }) {
  return (
    <div className="skeleton" style={{ height }} role="status" aria-label="Loading">
      <span className="sr-only">Loading…</span>
    </div>
  );
}

export function Empty({ title = "No data for this selection", children }) {
  return (
    <div className="state">
      <Inbox size={28} />
      <strong>{title}</strong>
      {children && <div>{children}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="state state-error" role="alert">
      <AlertTriangle size={28} />
      <strong>Could not load data</strong>
      <div>{error?.message || "Unknown error"}</div>
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          <Refresh size={16} /> Retry
        </button>
      )}
    </div>
  );
}

/** Renders loading / error / empty / content for a useApi() result. */
export function Async({ q, isEmpty, empty, height, children }) {
  if (q.error && !q.data) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (q.loading && !q.data) return <Skeleton height={height} />;
  if (!q.data || (isEmpty ? isEmpty(q.data) : Array.isArray(q.data) && q.data.length === 0)) return empty ?? <Empty />;
  return children(q.data);
}

export function LastUpdated({ q, refreshMs }) {
  const { tz } = useTz();
  const [, tick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => tick((n) => n + 1), 10000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="status" aria-live="polite">
      {q.error && q.data ? (
        <span className="down">Refresh failed: {q.error.message}.</span>
      ) : null}
      <span>
        Last updated <span className="num">{q.lastUpdated ? f.timeSec(q.lastUpdated, tz) : "—"}</span> {f.tzLabel(tz)}
        {refreshMs ? ` · every ${Math.round(refreshMs / 1000)} s` : ""}
      </span>
      <button type="button" className="btn" onClick={q.reload} aria-label="Refresh now" style={{ minHeight: 32, padding: "0 10px" }}>
        <Refresh size={14} />
      </button>
    </div>
  );
}
