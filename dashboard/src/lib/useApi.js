import { useCallback, useEffect, useRef, useState } from "react";
import { usePaused } from "./settings";

/**
 * Loads data with loading / error / last-updated state.
 * `refreshMs` polls in the background (skipped while the tab is hidden or the user paused
 * auto-refresh) and keeps the previous data on screen during a refresh, so nothing flickers.
 */
export function useApi(fetcher, deps, { refreshMs = 0, enabled = true } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: enabled, lastUpdated: null });
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const ctrlRef = useRef(null);
  const { paused } = usePaused();
  const pausedRef = useRef(paused);

  const load = useCallback(async (background = false) => {
    ctrlRef.current?.abort();
    const ctrl = new AbortController();
    ctrlRef.current = ctrl;
    if (!background) setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fetcherRef.current({ signal: ctrl.signal });
      if (!ctrl.signal.aborted) setState({ data, error: null, loading: false, lastUpdated: new Date() });
    } catch (error) {
      if (error.name !== "AbortError") setState((s) => ({ ...s, error, loading: false }));
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      setState({ data: null, error: null, loading: false, lastUpdated: null });
      return undefined;
    }
    setState({ data: null, error: null, loading: true, lastUpdated: null });
    load();
    let timer;
    if (refreshMs > 0) {
      timer = setInterval(() => {
        if (document.visibilityState === "visible" && !pausedRef.current) load(true);
      }, refreshMs);
    }
    return () => {
      clearInterval(timer);
      ctrlRef.current?.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled, refreshMs, load]);

  // On resume, catch up at once instead of waiting for the next tick.
  useEffect(() => {
    const wasPaused = pausedRef.current;
    pausedRef.current = paused;
    if (wasPaused && !paused && enabled && refreshMs > 0) load(true);
  }, [paused, enabled, refreshMs, load]);

  return { ...state, reload: () => load(false) };
}
