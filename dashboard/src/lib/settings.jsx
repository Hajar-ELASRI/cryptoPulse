import { createContext, useContext, useState } from "react";
import { useSearchParams } from "react-router-dom";

const TzContext = createContext({ tz: "UTC", setTz: () => {} });
const PauseContext = createContext({ paused: false, setPaused: () => {} });
const ThemeContext = createContext({ theme: "dark", toggleTheme: () => {} });

// index.html already set data-theme from storage or the system preference before first paint.
const readTheme = () => (document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark");

function readTz() {
  try {
    return localStorage.getItem("cp.tz") === "local" ? "local" : "UTC";
  } catch {
    return "UTC";
  }
}

export function TzProvider({ children }) {
  const [tz, setTzState] = useState(readTz);
  const setTz = (v) => {
    setTzState(v);
    try {
      localStorage.setItem("cp.tz", v);
    } catch {
      /* storage unavailable */
    }
  };
  // Auto-refresh pause is not stored: a reload always starts live.
  const [paused, setPaused] = useState(false);
  const [theme, setTheme] = useState(readTheme);
  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", next === "dark" ? "#10141b" : "#f3f5f9");
    try {
      localStorage.setItem("cp.theme", next);
    } catch {
      /* storage unavailable */
    }
  };
  return (
    <TzContext.Provider value={{ tz, setTz }}>
      <ThemeContext.Provider value={{ theme, toggleTheme }}>
        <PauseContext.Provider value={{ paused, setPaused }}>{children}</PauseContext.Provider>
      </ThemeContext.Provider>
    </TzContext.Provider>
  );
}

export const useTz = () => useContext(TzContext);
/** Pause/resume for every background poll (chart guidance: live views need a pause control). */
export const usePaused = () => useContext(PauseContext);
/** Dark ("night") or light ("day") theme, remembered in localStorage. */
export const useTheme = () => useContext(ThemeContext);

/** A filter kept in the URL (?symbol=…) so views can be shared and survive reloads. */
export function useParam(name, fallback = "") {
  const [params, setParams] = useSearchParams();
  const value = params.get(name) ?? fallback;
  const set = (v) =>
    setParams(
      (p) => {
        const next = new URLSearchParams(p);
        if (v === "" || v === null || v === undefined || v === fallback) next.delete(name);
        else next.set(name, v);
        return next;
      },
      { replace: true },
    );
  return [value, set];
}
