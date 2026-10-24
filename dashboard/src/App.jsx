import { useEffect, useRef } from "react";
import { Link, NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api, API_URL, USE_MOCKS } from "./api";
import { Pulse } from "./components/Icons";
import { DemoBadge, Notice, Segmented, ThemeToggle } from "./components/ui";
import { NAV } from "./lib/nav";
import { useTz } from "./lib/settings";
import { useApi } from "./lib/useApi";
import Alerts from "./pages/Alerts";
import Analytics from "./pages/Analytics";
import Landing from "./pages/Landing";
import Live from "./pages/Live";
import Replay from "./pages/Replay";
import Sentiment from "./pages/Sentiment";

function ApiStatus() {
  const q = useApi((o) => api.health(o), [], { refreshMs: 60000 });
  const ok = q.data && !q.error;
  const label = USE_MOCKS ? "Demo mode, no API" : q.loading && !q.data ? "Checking API…" : ok ? "API online" : "API offline";
  return (
    <span className="status" title={USE_MOCKS ? "Data comes from src/mocks" : API_URL}>
      <span className={`dot ${USE_MOCKS ? "" : ok ? "ok" : q.error ? "down" : ""}`} />
      {label}
    </span>
  );
}

function Dashboard() {
  const { tz, setTz } = useTz();
  const { pathname } = useLocation();
  const mainRef = useRef(null);
  useEffect(() => mainRef.current?.focus({ preventScroll: true }), [pathname]);

  return (
    <div className="app">
      <aside className="sidebar">
        <Link to="/" className="brand" aria-label="CryptoPulse home"><Pulse size={22} /> CryptoPulse</Link>
        <nav className="nav" aria-label="Dashboard">
          {NAV.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink key={item.to} to={item.to}>
                <Icon /> {item.label}
              </NavLink>
            );
          })}
        </nav>
        <div className="sidebar-foot muted">
          <Link to="/">About the project</Link>
          <span>Educational prototype, not financial advice.</span>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="topbar-right">
            <ApiStatus />
            <DemoBadge />
          </div>
          <div className="topbar-right">
            <Segmented label="Times shown in" options={[{ value: "UTC", label: "UTC" }, { value: "local", label: "Local" }]} value={tz} onChange={setTz} />
            <ThemeToggle />
          </div>
        </header>
        <main className="content" ref={mainRef} tabIndex={-1} style={{ outline: "none" }}>
          {USE_MOCKS && (
            <Notice demo>
              <b>Demo data.</b> These figures are synthetic fixtures shaped like Spark's output, used until the API is available. They are not market data.
            </Notice>
          )}
          <Routes>
            <Route index element={<Navigate to="live" replace />} />
            <Route path="live" element={<Live />} />
            <Route path="alerts" element={<Alerts />} />
            <Route path="sentiment" element={<Sentiment />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="replay" element={<Replay />} />
            <Route path="*" element={<Navigate to="live" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

/** Links shared before the landing page existed (/live?symbol=…) keep working. */
function MovedToApp() {
  const { pathname, search } = useLocation();
  return <Navigate to={`/app${pathname}${search}`} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/app/*" element={<Dashboard />} />
      {["/live", "/alerts", "/sentiment", "/analytics", "/replay"].map((p) => (
        <Route key={p} path={p} element={<MovedToApp />} />
      ))}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
