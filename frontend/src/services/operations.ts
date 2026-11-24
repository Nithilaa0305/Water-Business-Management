import { api, ApiError } from "./api";

// Keep the original request across reloads in this tab. A lost response must not
// turn into a new sale/payment when the cashier presses the same action again.
const inFlight = new Set<string>();
function operationKey(path: string, token: string) {
  const actor = (() => {
    try {
      const encoded = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
      return String(JSON.parse(atob(encoded)).user_id || "current");
    } catch { return "current"; }
  })();
  return `pending-operation:${actor}:${path}`;
}

function pendingOperation(path: string, token: string): {draft: string; id: string} | null {
  const stored = sessionStorage.getItem(operationKey(path, token));
  return stored ? JSON.parse(stored) : null;
}

export function hasPendingOperation(path: string, token: string) {
  return !!pendingOperation(path, token);
}

export function retryOperation<T>(path: string, token: string): Promise<T> {
  const pending = pendingOperation(path, token);
  if (!pending) return Promise.reject(new Error("No unconfirmed request."));
  return submitOnce<T>(path, JSON.parse(pending.draft), token);
}

export async function submitOnce<T>(path: string, payload: Record<string, unknown>, token: string): Promise<T> {
  const key = operationKey(path, token);
  if (inFlight.has(key)) throw new Error("This request is still being sent.");
  const draft = JSON.stringify(payload);
  const pending = pendingOperation(path, token);
  if (pending && pending.draft !== draft) {
    throw new Error("A previous request is unconfirmed. Check or retry that original request before recording a new one.");
  }
  const id = pending?.id ?? (typeof crypto.randomUUID === "function" ? crypto.randomUUID() : Array.from(crypto.getRandomValues(new Uint32Array(4)), (n) => n.toString(16)).join("-"));
  sessionStorage.setItem(key, JSON.stringify({ draft, id }));
  inFlight.add(key);
  try {
    const result = await api.post<T>(path, { ...payload, operation_id: id }, token);
    sessionStorage.removeItem(key);
    return result;
  } catch (error) {
    // Validation errors prove the transaction did not post. Transport errors,
    // server errors and duplicate-in-flight conflicts are ambiguous; retain key.
    if (error instanceof ApiError && [400, 404, 422].includes(error.status)) sessionStorage.removeItem(key);
    if (error instanceof ApiError && error.status === 409 && (error.code === "stale_balance" || error.message.startsWith("Price changed"))) {
      sessionStorage.removeItem(key);
    }
    throw error;
  } finally {
    inFlight.delete(key);
  }
}
