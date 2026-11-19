const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

type RequestOptions = RequestInit & { token?: string | null };

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { token, ...init } = options;
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || body?.message || `Request failed (${response.status})`);
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}

export const api = {
  signIn: (pin: string, role: string) =>
    request<{ access_token: string; user?: { name?: string; role?: string } }>("/auth/sign-in", {
      method: "POST",
      body: JSON.stringify({ pin, role }),
    }),
  signOut: (token: string) => request("/auth/sign-out", { method: "POST", token }),
  get: <T>(path: string, token: string) => request<T>(path, { token }),
  post: <T>(path: string, body: unknown, token: string) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body), token }),
};
