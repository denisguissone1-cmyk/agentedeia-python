export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// Endpoints que tratam o 401 por conta própria (login mostra erro; /me é o probe do guard).
const SEM_REDIRECT_401 = new Set(["/login", "/me"])

export async function api<T = unknown>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  })
  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) {
    if (
      res.status === 401 &&
      !SEM_REDIRECT_401.has(path) &&
      typeof window !== "undefined" &&
      window.location.pathname !== "/login"
    ) {
      // sessão expirada/ausente numa rota autenticada → desloga na hora
      window.location.href = "/login"
    }
    const detail = (data && (data as { detail?: string }).detail) || res.statusText
    throw new ApiError(res.status, detail)
  }
  return data as T
}

export const post = <T = unknown>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined })
