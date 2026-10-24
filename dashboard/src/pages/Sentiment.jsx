import { api, REFRESH_MS } from "../api";
import { Async, DateTimeField, Empty, LastUpdated, Notice, PageHead, Select, SentimentLabel, SymbolPicker } from "../components/ui";
import * as f from "../lib/format";
import { useParam, useTz } from "../lib/settings";
import { useApi } from "../lib/useApi";

const LABELS = [{ value: "", label: "All" }, { value: "positive", label: "Positive" }, { value: "neutral", label: "Neutral" }, { value: "negative", label: "Negative" }];

// The API has no article title (docs/api.md), so name the item by its publisher:
// "CoinDesk: Bitcoin, Ethereum, …" -> "CoinDesk article"; Reddit items are posts.
function itemName(s) {
  if (s.title) return s.title;
  if (s.source_topic === "crypto-social") return s.source ? `Reddit post in ${s.source}` : "Reddit post";
  const publisher = (s.source || "").split(":")[0].replace(/\.com( News)?$/i, "").trim();
  return publisher ? `${publisher} article` : "News article";
}

function ScoreBar({ score }) {
  const s = Math.max(-1, Math.min(1, f.toNum(score) ?? 0));
  const color = s > 0.05 ? "var(--color-up)" : s < -0.05 ? "var(--color-down)" : "var(--color-neutral)";
  const style = s >= 0 ? { left: "50%", width: `${s * 50}%` } : { left: `${50 + s * 50}%`, width: `${-s * 50}%` };
  return (
    <div className="score-bar" role="img" aria-label={`Score ${f.decimal(s, 2)} on a scale from −1 to +1`}>
      <span className="score-fill" style={{ ...style, background: color }} />
    </div>
  );
}

export default function Sentiment() {
  const { tz } = useTz();
  const [symbol, setSymbol] = useParam("symbol", "");
  const [label, setLabel] = useParam("label", "");
  const [from, setFrom] = useParam("from", "");
  const [to, setTo] = useParam("to", "");
  const q = useApi((o) => api.sentiment({ symbol, label, from, to, limit: 100 }, o), [symbol, label, from, to], { refreshMs: REFRESH_MS });

  return (
    <>
      <PageHead title="Sentiment" description="News and social posts scored by the VADER sentiment service, linked to trading pairs (collection sentiment).">
        <SymbolPicker value={symbol} onChange={setSymbol} allowAll />
        <Select label="Label" value={label} onChange={setLabel} options={LABELS} />
        <DateTimeField label="From" value={from} onChange={setFrom} />
        <DateTimeField label="To" value={to} onChange={setTo} />
      </PageHead>
      <LastUpdated q={q} refreshMs={REFRESH_MS} />

      <Notice>
        Sentiment next to prices is an <b>observed correlation, not a cause</b>. VADER is a general English model: it can misread crypto slang and sarcasm.
        Nothing here is financial advice.
      </Notice>

      <section className="card" aria-label="Scored articles and posts">
        <Async q={q} height={300} empty={<Empty title="No scored articles for this selection">Try another symbol, label or period.</Empty>}>
          {(rows) => (
            <>
              <div className="card-head">
                <h2>{rows.length} item{rows.length > 1 ? "s" : ""}</h2>
                <span className="hint">
                  {f.dateTime(rows[rows.length - 1].event_time, tz)} → {f.dateTime(rows[0].event_time, tz)} {f.tzLabel(tz)}
                </span>
              </div>
              <ul className="news plain-list">
                {rows.map((s) => (
                  <li key={s.event_id} className="news-item">
                    <div>
                      {s.url ? (
                        <a className="news-title" href={s.url} target="_blank" rel="noreferrer noopener">{itemName(s)}</a>
                      ) : (
                        <span className="news-title">{itemName(s)}</span>
                      )}
                      <div className="news-meta">
                        <span className="num">{f.dateTime(s.event_time, tz)} {f.tzLabel(tz)}</span>
                        <span>{s.source_topic === "crypto-social" ? "Reddit" : "News feed"}</span>
                        {!s.title && <span className="num" title="Source event id">{s.source_event_id}</span>}
                        {(s.trade_symbols || s.symbols || []).map((sym) => (
                          <span key={sym} className="badge badge-neutral">{sym}</span>
                        ))}
                      </div>
                    </div>
                    <div className="score">
                      <SentimentLabel value={s.label} />
                      <span className="num score-value">score {f.decimal(s.score, 2)}</span>
                      <ScoreBar score={s.score} />
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Async>
      </section>
    </>
  );
}
