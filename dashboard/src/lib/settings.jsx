import { createContext, useContext, useState } from "react";
import { useSearchParams } from "react-router-dom";

const TzContext = createContext({ tz: "UTC", setTz: () => {} });

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
  return <TzContext.Provider value={{ tz, setTz }}>{children}</TzContext.Provider>;
}

export const useTz = () => useContext(TzContext);

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
