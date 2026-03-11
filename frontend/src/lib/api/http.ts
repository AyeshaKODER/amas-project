// ---------------------------------------------------------------------------
// Centralized HTTP client for the FastAPI backend
// ---------------------------------------------------------------------------

const TOKEN_KEY = 'auth_token';

// ---- Base URL resolution ----------------------------------------------------

function resolveBaseUrl(): string {
  // 1. Vite env
  const envUrl =
    typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_URL
      ? String(import.meta.env.VITE_API_URL)
      : '';

  const raw = envUrl || 'http://localhost:8000';
  const base = raw.endsWith('/') ? raw.slice(0, -1) : raw;
  return `${base}/api/v1`;
}

let BASE_URL = resolveBaseUrl();

/** Override the base URL at runtime (e.g. from Settings page). */
export function setBaseUrl(url: string) {
  BASE_URL = url;
}

export function getBaseUrl(): string {
  return BASE_URL;
}

// ---- Token helpers ----------------------------------------------------------

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

// ---- Typed API error --------------------------------------------------------

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

// ---- Internal helpers -------------------------------------------------------

async function handleResponse<T>(response: Response): Promise<T> {
  if (response.status === 401) {
    clearToken();
    localStorage.removeItem('amas_user');
    // Redirect only if we're in a browser context and not already on /login
    if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
      window.location.href = '/login';
    }
    throw new ApiError(401, 'Unauthorized – session expired');
  }

  let body: unknown;
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    body = await response.json();
  } else {
    body = await response.text();
  }

  if (!response.ok) {
    const msg =
      (body && typeof body === 'object' && 'detail' in body)
        ? String((body as { detail: string }).detail)
        : response.statusText;
    throw new ApiError(response.status, msg, body);
  }

  return body as T;
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

// ---- Public HTTP methods ----------------------------------------------------

export async function get<T = unknown>(endpoint: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    headers: { ...authHeaders() },
  });
  return handleResponse<T>(res);
}

export async function post<T = unknown>(endpoint: string, data?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: data !== undefined ? JSON.stringify(data) : undefined,
  });
  return handleResponse<T>(res);
}

export async function put<T = unknown>(endpoint: string, data?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: data !== undefined ? JSON.stringify(data) : undefined,
  });
  return handleResponse<T>(res);
}

export async function patch<T = unknown>(endpoint: string, data?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: data !== undefined ? JSON.stringify(data) : undefined,
  });
  return handleResponse<T>(res);
}

export async function del<T = unknown>(endpoint: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    method: 'DELETE',
    headers: { ...authHeaders() },
  });
  return handleResponse<T>(res);
}

/**
 * POST with `application/x-www-form-urlencoded` body
 * (used by FastAPI's OAuth2PasswordRequestForm).
 */
export async function postForm<T = unknown>(
  endpoint: string,
  data: Record<string, string>,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      ...authHeaders(),
    },
    body: new URLSearchParams(data).toString(),
  });
  return handleResponse<T>(res);
}
