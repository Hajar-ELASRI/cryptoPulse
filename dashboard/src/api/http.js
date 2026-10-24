// Thin fetch wrapper for Mossab's API: query params, readable errors, list normalisation.

export const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8081").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function query(params) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params || {})) {
    if (v !== undefined && v !== null && v !== "") q.set(k, v);
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

export async function request(path, params, { signal } = {}) {
  // Built outside the try so a client-side bug is never reported as "API unreachable".
  const url = `${API_URL}${path}${query(params)}`;
  let res;
  try {
    res = await fetch(url, { signal, headers: { Accept: "application/json" } });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new ApiError(`Cannot reach the API at ${API_URL}. Is it running?`, 0);
  }
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      message = body.message || body.error || message;
    } catch {
      /* body was not JSON */
    }
    throw new ApiError(message, res.status);
  }
  return res.status === 204 ? null : res.json();
}

// Accept a plain array, a Spring Page ({content}) or {items}.
export function asList(body) {
  if (Array.isArray(body)) return body;
  if (body && Array.isArray(body.content)) return body.content;
  if (body && Array.isArray(body.items)) return body.items;
  return [];
}
