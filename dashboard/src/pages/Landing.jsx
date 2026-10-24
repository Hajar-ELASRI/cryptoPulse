import { Link } from "react-router-dom";
import { api, REFRESH_MS, SYMBOLS, USE_MOCKS } from "../api";
import AlertList from "../components/AlertList";
import { ArrowRight, Pulse } from "../components/Icons";
import { Change, DemoBadge, Skeleton, ThemeToggle } from "../components/ui";
import * as f from "../lib/format";
import { NAV } from "../lib/nav";
import { useTz } from "../lib/settings";
import { useApi } from "../lib/useApi";

const FLOW = [
  { title: "Collect", text: "Binance trades, crypto news feeds and Reddit posts" },
  { title: "Stream", text: "Kafka topics carry every event as it arrives" },
  { title: "Compute", text: "Spark builds one-minute indicators, alerts and sentiment" },
  { title: "Store", text: "MongoDB keeps live and replay results apart" },
  { title: "Serve", text: "A Spring Boot API exposes the results" },
  { title: "Show", text: "This dashboard, refreshed every 30 seconds" },
];

const TEAM = [
  { name: "Hajar", role: "Data collection and infrastructure", text: "Binance, news and Reddit collectors feeding Kafka" },
  { name: "Ali", role: "Spark processing", text: "Indicators, alerts, replay and sentiment jobs" },
  { name: "Mossab", role: "REST API", text: "Spring Boot routes over MongoDB" },
  { name: "Mohammed", role: "Dashboard and demo", text: "This interface and the demo scenario" },
];

const W = 600;
const H = 132;

/** The last hour of closes as one line; it draws itself once when the page loads. */
function Trace({ rows }) {
  const closes = [...rows].reverse().map((r) => f.toNum(r.close_price)).filter((v) => v != null);
  if (closes.length < 2) return null;
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const span = max - min || 1;
  const pts = closes.map((v, i) => [(i / (closes.length - 1)) * W, 8 + (1 - (v - min) / span) * (H - 16)]);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const [lx, ly] = pts[pts.length - 1];
  return (
    <svg className="trace" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Close price over the last ${closes.length} minutes, from ${f.price(closes[0])} to ${f.price(closes[closes.length - 1])}`}>
      <path className="area" d={`${line} L${W} ${H} L0 ${H} Z`} />
      <path className="line" d={line} pathLength="1" />
      <circle cx={lx} cy={ly} r="5" />
    </svg>
  );
}

function OtherPair({ symbol }) {
  const q = useApi((o) => api.live({ symbol, limit: 2 }, o), [symbol], { refreshMs: REFRESH_MS });
  const last = q.data?.[0];
  return (
    <div className="pulse-other">
      <span className="muted">{f.baseOf(symbol)} / {f.quoteOf(symbol)}</span>
      <span>
        <b>{last ? f.price(last.close_price) : "—"}</b> {last && <Change value={last.change_pct} />}
      </span>
    </div>
  );
}

function LivePulse() {
  const { tz } = useTz();
  const symbol = SYMBOLS[0];
  const q = useApi((o) => api.live({ symbol, limit: 60 }, o), [symbol], { refreshMs: REFRESH_MS });
  const last = q.data?.[0];

  return (
    <section className="pulse" aria-labelledby="pulse-title">
      <div className="pulse-top">
        <h2 id="pulse-title" className="pulse-pair">{f.baseOf(symbol)} / {f.quoteOf(symbol)}</h2>
        {USE_MOCKS ? <DemoBadge /> : <span className="status"><span className="dot ok" /> Live from the pipeline</span>}
      </div>
      {q.error && !q.data ? (
        <p className="state-error">The price could not be loaded: {q.error.message}. Check that the API is running, then reload.</p>
      ) : !last ? (
        <Skeleton height={220} />
      ) : (
        <>
          <p className="pulse-price">
            {f.price(last.close_price)}<small>{f.quoteOf(symbol)}</small>
          </p>
          <div className="pulse-meta">
            <Change value={last.change_pct} />
            <span>vs the minute before</span>
            <span>{f.integer(last.trade_count)} trades in the minute to {f.time(last.window_end, tz)} {f.tzLabel(tz)}</span>
          </div>
          <Trace rows={q.data} />
        </>
      )}
      <div className="pulse-others">
        {SYMBOLS.slice(1).map((s) => <OtherPair key={s} symbol={s} />)}
      </div>
    </section>
  );
}

function LatestAlerts() {
  const q = useApi((o) => api.alerts({ limit: 3 }, o), [], { refreshMs: REFRESH_MS });
  if (q.error && !q.data) return <p className="muted">Alerts could not be loaded: {q.error.message}.</p>;
  if (!q.data) return <Skeleton height={200} />;
  if (!q.data.length) return <p className="muted">No alert yet. One appears as soon as a threshold is crossed.</p>;
  return <AlertList alerts={q.data.slice(0, 3)} compact />;
}

export default function Landing() {
  return (
    <div className="landing">
      <header className="site-head">
        <div className="wrap">
          <Link to="/" className="brand"><Pulse size={22} /> CryptoPulse</Link>
          <nav className="site-nav" aria-label="Site">
            <a className="link" href="#views">What you can check</a>
            <a className="link" href="#how">How it works</a>
            <a className="link" href="#team">Team</a>
            <ThemeToggle />
            <Link to="/app/live" className="btn btn-primary">Open dashboard</Link>
          </nav>
        </div>
      </header>

      <main>
        <div className="wrap hero">
          <div>
            <h1>Bitcoin and Ether, minute by minute.</h1>
            <p className="hero-lede">
              CryptoPulse turns the Binance trade stream, crypto news and Reddit posts into one-minute market figures, alerts that explain themselves and sentiment scores.
            </p>
            <div className="hero-actions">
              <Link to="/app/live" className="btn btn-primary">Open the live dashboard</Link>
              <a href="#how" className="btn">See how it works</a>
            </div>
          </div>
          <LivePulse />
        </div>

        <section className="section" id="views" aria-labelledby="views-title">
          <div className="wrap split">
            <div>
              <div className="section-head">
                <div>
                  <h2 id="views-title">What you can check</h2>
                  <p>Five views of the same data. Filters stay in the address, so any view can be shared.</p>
                </div>
              </div>
              <ul className="views plain-list">
                {NAV.map((item) => {
                  const Icon = item.icon;
                  return (
                    <li key={item.to}>
                      <Link to={item.to} className="view-row">
                        <span className="view-icon"><Icon /></span>
                        <span>
                          <strong>{item.label}</strong>
                          <span className="desc">{item.desc}</span>
                        </span>
                        <ArrowRight className="go" />
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
            <div>
              <div className="section-head">
                <div>
                  <h2>Latest alerts</h2>
                  <p>Each alert says what was measured, the threshold it crossed and the usual level.</p>
                </div>
              </div>
              <LatestAlerts />
              <p><Link to="/app/alerts">See all alerts</Link></p>
            </div>
          </div>
        </section>

        <section className="section" id="how" aria-labelledby="how-title">
          <div className="wrap">
            <div className="section-head">
              <div>
                <h2 id="how-title">How the data moves</h2>
                <p>From a trade on Binance to a point on the chart in about two minutes.</p>
              </div>
            </div>
            <ol className="flow plain-list">
              {FLOW.map((s) => (
                <li key={s.title}>
                  <strong>{s.title}</strong>
                  <span>{s.text}</span>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="section" id="team" aria-labelledby="team-title">
          <div className="wrap">
            <div className="section-head">
              <div>
                <h2 id="team-title">Who built it</h2>
                <p>A four-person big data project. Each member owns one stage of the pipeline.</p>
              </div>
            </div>
            <div className="team">
              {TEAM.map((m) => (
                <div key={m.name} className="member">
                  <strong>{m.name}</strong>
                  <span className="role">{m.role}</span>
                  <span>{m.text}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>

      <footer className="site-foot">
        <div className="wrap">
          <span>CryptoPulse, a big data course project.</span>
          <span>{USE_MOCKS ? "Figures shown are demo data until the API is connected. " : ""}Educational prototype, not financial advice.</span>
        </div>
      </footer>
    </div>
  );
}
