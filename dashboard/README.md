# CryptoPulse dashboard (Mohammed)

React (Vite) dashboard for the five views of the project: **Live, Alerts, Sentiment, Analytics, Replay**. It only reads Mossab's API. It never connects to MongoDB or Kafka and never recalculates indicators or alerts.

## Run

Requires Node 20+.

```sh
cd dashboard
npm install
cp .env.example .env.local   # optional, defaults are fine for the demo
npm run dev                  # http://localhost:5173
```

`npm run build` makes a static build in `dist/`; `npm run lint` checks the code.

## Configuration (`.env.local`)

| Variable | Default | Meaning |
|---|---|---|
| `VITE_USE_MOCKS` | `true` | `true`: synthetic demo fixtures. `false`: Mossab's API. |
| `VITE_API_URL` | `http://localhost:8081` | API base URL (port to confirm with Mossab; Spark UI uses 8080). |
| `VITE_REFRESH_MS` | `30000` | Polling interval of Live, Alerts and Sentiment. |
| `VITE_SYMBOLS` | `BTCUSDT,ETHUSDT` | Symbols offered in the pickers. |

## Demo data vs real data

Until the API exists, `VITE_USE_MOCKS=true` serves the files in `src/mocks/fixtures/`. They follow the field names of `docs/contracts.md` (Spark output contracts) and the alert sentences of `spark/cryptopulse_spark/gold.py`, and they are generated deterministically by `npm run mocks` (`scripts/generate-mocks.mjs`). In this mode the page shows a **DEMO DATA** badge and a banner, so simulated data is never mistaken for real data. The fixtures are loaded only in demo mode.

To switch to the real API: set `VITE_USE_MOCKS=false` and `VITE_API_URL`, restart `npm run dev`. If a route or field differs from `docs/dashboard-api-needs.md`, adapt `src/api/index.js` only.

## Structure

```
src/
  api/          http.js (fetch, errors, lists) · index.js (routes, mock switch)
  mocks/        server.js (filters fixtures like the API would) · fixtures/*.json
  lib/          format.js (numbers, %, UTC/local dates) · useApi.js (loading/error/polling) · settings.jsx (time zone, URL filters)
  components/   ui.jsx (states, stats, pickers) · MarketCharts.jsx · AlertList.jsx · Icons.jsx
  pages/        Live · Alerts · Sentiment · Analytics · Replay
design-system/  ui-ux-pro-max output used for colours, fonts and spacing (MASTER.md)
```

## UI rules followed

From `design-system/cryptopulse/MASTER.md` (ui-ux-pro-max): dark Swiss/minimal style, amber primary, Fira Sans text, Fira Code tabular figures, dense spacing. Every view has loading (skeleton), empty and error (with retry) states; up/down and severity are shown with an icon or text as well as colour; charts have a legend, a tooltip and a data-table alternative; filters live in the URL so a view can be shared; times are labelled UTC or local (toggle in the top bar); motion respects `prefers-reduced-motion`; layout tested at 390 px and 1440 px.

## Not done yet

- Real API integration (waits for Mossab's routes, brief task 8).
- SSE (polling every 30 s is used instead).
