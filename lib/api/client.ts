const DEFAULT_API_URL = "http://127.0.0.1:8000";
const TOKEN_KEY = "weefarm_token";

function isLocalHost(hostname: string) {
  return hostname === "localhost" || hostname === "127.0.0.1";
}

function shouldUseDemoMode() {
  if (process.env.NEXT_PUBLIC_DEMO_MODE === "true") return true;
  if (typeof window === "undefined") return false;

  const configuredApi = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (configuredApi) return false;

  // On hosted previews/prod without a configured backend URL, force demo mode.
  return !isLocalHost(window.location.hostname);
}

export type ApiErrorPayload = {
  message: string;
  status: number;
  details?: string | string[] | Record<string, unknown>;
};

export class ApiError extends Error {
  status: number;
  details?: ApiErrorPayload["details"];

  constructor(payload: ApiErrorPayload) {
    super(payload.message);
    this.status = payload.status;
    this.details = payload.details;
  }
}

let unauthorizedHandler: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler;
}

export function getApiBaseUrl() {
  return process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL;
}

export function getStoredToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function storeToken(token: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}

export type RequestOptions = Omit<RequestInit, "body"> & {
  body?: Record<string, unknown> | FormData | string | null;
  auth?: boolean;
};

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = `${getApiBaseUrl()}${path}`;
  const headers = new Headers(options.headers || {});
  const hasBody = options.body !== undefined && options.body !== null;

  if (options.auth !== false) {
    const token = getStoredToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  let body: BodyInit | undefined;
  if (hasBody) {
    if (options.body instanceof FormData) {
      body = options.body;
    } else if (typeof options.body === "string") {
      body = options.body;
      headers.set("Content-Type", "application/json");
    } else {
      body = JSON.stringify(options.body);
      headers.set("Content-Type", "application/json");
    }
  }

  if (shouldUseDemoMode() && typeof window !== "undefined") {
    const { mockApiFetch } = await import("@/lib/api/mock");
    return mockApiFetch<T>(path, {
      ...options,
      headers,
      body: options.body,
      auth: options.auth,
    });
  }

  const response = await fetch(url, {
    ...options,
    headers,
    body,
  });

  if (response.status === 401 && unauthorizedHandler) {
    unauthorizedHandler();
  }

  if (!response.ok) {
    let message = response.statusText || "Request failed";
    let details: ApiErrorPayload["details"];

    try {
      const data = (await response.json()) as { detail?: unknown; message?: string };
      if (typeof data.message === "string") message = data.message;
      if (typeof data.detail === "string") message = data.detail;
      const detail = data.detail;
      if (typeof detail === "string" || Array.isArray(detail) || (detail && typeof detail === "object")) {
        details = detail as ApiErrorPayload["details"];
      }
    } catch {
      // ignore parsing errors
    }

    throw new ApiError({ message, status: response.status, details });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
