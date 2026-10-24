import { useEffect, useRef } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api, API_URL, USE_MOCKS } from "./api";
import { Activity, BarChart, Bell, History, Newspaper, Pulse } from "./components/Icons";
import { DemoBadge, Notice, Segmented } from "./components/ui";
import { useTz } from "./lib/settings";
import { useApi } from "./lib/useApi";
import Alerts from "./pages/Alerts";
import Analytics from "./pages/Analytics";
import Live from "./pages/Live";
import Replay from "./pages/Replay";
import Sentiment from "./pages/Sentiment";

const NAV = [
  { to: "/live", label: "Live", icon: Activity },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/sentiment", label: "Sentiment", icon: Newspaper },
  { to: "/analytics", label: "Analytics", icon: BarChart },
  { to: "/replay", label: "Replay", icon: History },
];

function ApiStatus() {
  const q = useApi((o) => api.health(o), [], { refreshMs: 60000 });
  const ok = q.data && !q.error;
  const label = USE_MOCKS ? "Demo mode (no API)" : q.loading && !q.data ? "Checking API…" : ok ? "API online" : "API offline";
  return (
    <span className="status" title={USE_MOCKS ? "Data comes from src/mocks" : API_URL}>
      <span className={`dot ${USE_MOCKS ? "" : ok ? "ok" : q.error ? "down" : ""}`} />
      {label}
    </span>
  );
}

export default function App() {
  const { tz, setTz } = useTz();
  const { pathname } = useLocation();
  const mainRef = useRef(null);
  useEffect(() => mainRef.current?.focus({ preventScroll: true }), [pathname]);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand"><Pulse size={22} /> CryptoPulse</div>
        <nav className="nav" aria-label="Main">
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
          <span>Binance · RSS · Reddit → Kafka → Spark → MongoDB → API</span>
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
          </div>
        </header>
        <main className="content" ref={mainRef} tabIndex={-1} style={{ outline: "none" }}>
          {USE_MOCKS && (
            <Notice demo>
              <b>Demo data.</b> These figures are synthetic fixtures shaped like Spark's output, used until the API is available. They are not market data.
            </Notice>
          )}
          <Routes>
            <Route path="/" element={<Navigate to="/live" replace />} />
            <Route path="/live" element={<Live />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/sentiment" element={<Sentiment />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/replay" element={<Replay />} />
            <Route path="*" element={<Navigate to="/live" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
