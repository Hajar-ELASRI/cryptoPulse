# CryptoPulse dashboard (Mohammed)

React (Vite) front end of the project: a **landing page** (`/`) that presents CryptoPulse with the live price, and the **dashboard** (`/app/...`) with five views: **Live, Alerts, Sentiment, Analytics, Replay**. It only reads Mossab's API. It never connects to MongoDB or Kafka and never recalculates indicators or alerts.

## Run

Requires Node 20+.

```sh
cd dashboard
npm install
cp .env.example .env.local   # optional, defaults are fine for the demo
npm run dev                  # http://localhost:5173 (landing), /app/live (dashboard)
```

Older links such as `/live?symbol=ETHUSDT` redirect to `/app/live?symbol=ETHUSDT`.

`npm run build` makes a static build in `dist/`; `npm run lint` checks the code.

## Configuration (`.env.local`)

| Variable | Default | Meaning |
|---|---|---|
| `VITE_USE_MOCKS` | `true` | `true`: synthetic demo fixtures. `false`: Mossab's API. |
| `VITE_API_URL` | `http://localhost:8081` | API base URL (port to confirm with Mossab; Spark UI uses 8080). |
| `VITE_REFRESH_MS` | `30000` | Polling interval of Live, Alerts and Sentiment. |
| `VITE_SYMBOLS` | `BTCUSDT,ETHUSDT` | Symbols offered in the pickers. |

## Demo data vs real data

Until the API exists, `VITE_USE_MOCKS=true` serves the files in `src/mocks/fixtures/`. They follow the field names of `docs/contracts.md` (Spark output contracts) and the alert sentences of `spark/cryptopulse_spark/gold.py`, and they are generated deterministically by `npm run mocks` (`scripts/generate-mocks.mjs`). In this mode the page shows a **Demo data** badge and a banner, so simulated data is never mistaken for real data. The fixtures are loaded only in demo mode.

To switch to the real API: set `VITE_USE_MOCKS=false` and `VITE_API_URL`, restart `npm run dev`. If a route or field differs from `docs/dashboard-api-needs.md`, adapt `src/api/index.js` only.

## Structure

```
src/
  api/          http.js (fetch, errors, lists) · index.js (routes, mock switch)
  mocks/        server.js (filters fixtures like the API would) · fixtures/*.json
  lib/          format.js (numbers, %, UTC/local dates) · useApi.js (loading/error/polling, pause) · settings.jsx (time zone, theme, pause, URL filters) · nav.js (page list)
  components/   ui.jsx (states, stats, pickers, theme toggle) · MarketCharts.jsx · AlertList.jsx · Icons.jsx
  pages/        Landing · Live · Alerts · Sentiment · Analytics · Replay
design-system/  colours, fonts, spacing and rules for both themes (MASTER.md)
```

## UI rules followed

See `design-system/cryptopulse/MASTER.md`. Two themes, "night" (graphite, periwinkle accent) and "day" (cool paper, indigo accent), switched from the top bar and remembered; the system preference is used the first time. Bricolage Grotesque for titles and the hero price, IBM Plex Sans with tabular figures for everything else. Every view has loading (skeleton), empty and error (with retry) states; up/down and severity are shown with an icon or text as well as colour; charts have a legend, a tooltip and a data-table alternative; filters live in the URL so a view can be shared; times are labelled UTC or local; auto-refresh can be paused; controls are at least 44 px; under 640 px the pages move to a bottom tab bar; motion respects `prefers-reduced-motion`.

## Not done yet

- Real API integration (waits for Mossab's routes, brief task 8).
- SSE (polling every 30 s is used instead).
