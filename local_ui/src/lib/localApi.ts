interface Bootstrap {
  matchId: string;
  token: string;
}

export class ApiError extends Error {
  code: string;
  details: unknown;
  status: number;

  constructor(status: number, code: string, message: string, details: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function getBootstrap(): Bootstrap {
  const params = new URLSearchParams(window.location.search);
  const matchId = params.get("match_id") ?? "";
  const token = params.get("token") ?? "";
  if (!matchId || !token) {
    throw new ApiError(400, "missing_bootstrap", "Parametres match_id/token absents.");
  }
  return { matchId, token };
}

export async function apiGet<T>(path: string, token: string): Promise<T> {
  return request<T>(path, token);
}

export async function apiPost<T>(path: string, token: string, body: unknown): Promise<T> {
  return request<T>(path, token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
}

async function request<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-Enduraw-Local-Token", token);
  const response = await fetch(path, { ...init, headers });
  const payload = await readPayload(response);
  if (!response.ok || payload?.ok === false) {
    const error = payload?.error;
    throw new ApiError(
      response.status,
      stringOr(error?.code, "api_error"),
      stringOr(error?.message, "Erreur API locale."),
      error?.details ?? null,
    );
  }
  return payload as T;
}

interface ApiPayload {
  ok?: boolean;
  error?: {
    code?: unknown;
    message?: unknown;
    details?: unknown;
  };
}

async function readPayload(response: Response): Promise<ApiPayload | null> {
  try {
    return await response.json();
  } catch (_err) {
    return null;
  }
}

function stringOr(value: unknown, fallback: string): string {
  return typeof value === "string" && value ? value : fallback;
}
