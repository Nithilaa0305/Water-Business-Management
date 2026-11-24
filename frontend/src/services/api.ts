const API_URL = import.meta.env.VITE_API_URL || "";

type RequestOptions = RequestInit & { token?: string | null };
export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) { super(message); }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { token, ...init } = options;
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    const message = typeof detail === "string" ? detail : detail?.message || body?.message;
    throw new ApiError(response.status, message || `Request failed (${response.status})`, detail?.error);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export const api = {
  signIn: (pin: string, role: string) =>
    request<{ access_token: string; user?: { name?: string; role?: string } }>("/auth/sign-in", {
      method: "POST", body: JSON.stringify({ pin, role }),
    }),
  signOut: (token: string) => request("/auth/sign-out", { method: "POST", token }),
  get: <T>(path: string, token: string) => request<T>(path, { token }),
  post: <T>(path: string, body: unknown, token: string) =>
    request<T>(path, { method: "POST", token, body: JSON.stringify(body) }),
};
