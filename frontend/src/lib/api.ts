export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function api<T = unknown>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  })
  const data = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) {
    const detail = (data && (data as { detail?: string }).detail) || res.statusText
    throw new ApiError(res.status, detail)
  }
  return data as T
}

export const post = <T = unknown>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined })
