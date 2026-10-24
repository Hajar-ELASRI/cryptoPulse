import { Activity, BarChart, Bell, History, Newspaper } from "../components/Icons";

/** The five dashboard pages, used by the sidebar and by the landing page. */
export const NAV = [
  { to: "/app/live", label: "Live", icon: Activity, desc: "Price, volume and trades of the last hour, minute by minute" },
  { to: "/app/alerts", label: "Alerts", icon: Bell, desc: "Every volume spike, price move and large trade, with the reason" },
  { to: "/app/sentiment", label: "Sentiment", icon: Newspaper, desc: "News and Reddit posts scored from negative to positive" },
  { to: "/app/analytics", label: "Analytics", icon: BarChart, desc: "Any period summarised: change, range, volume, alerts" },
  { to: "/app/replay", label: "Replay", icon: History, desc: "Past periods processed again with the same rules" },
];
