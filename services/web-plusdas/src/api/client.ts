import type { ApiError } from './types/errors';
import { getRuntimeConfig } from '@/shared/config/runtime';

// Same-origin API bases from runtime config, never build-time values: backend-ot at `/api`,
// the powerflow simulator at `/powerflow-api` (nginx/Vite forward it to powerflow's /api).
export const BASE_URL = getRuntimeConfig().apiBaseUrl;
export const POWERFLOW_BASE_URL = getRuntimeConfig().powerflowBaseUrl;

async function send(baseUrl: string, path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${baseUrl}${path}`, {
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({
      code: String(response.status),
      message: response.statusText,
    }));
    throw error;
  }
  return response;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return (await send(BASE_URL, path, init)).json();
}

// One API's verbs on its own base URL.
export function createClient(baseUrl: string) {
  const json = async <T>(path: string, init?: RequestInit): Promise<T> =>
    (await send(baseUrl, path, init)).json();
  const nothing = async (path: string, init?: RequestInit): Promise<void> => {
    await send(baseUrl, path, init);
  };
  return {
    get: <T>(path: string) => json<T>(path),
    // A text body, e.g. text/csv.
    getText: async (path: string): Promise<string> => (await send(baseUrl, path)).text(),
    post: <T>(path: string, body: unknown) =>
      json<T>(path, { method: 'POST', body: JSON.stringify(body) }),
    put: <T>(path: string, body: unknown) =>
      json<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
    delete: (path: string) => nothing(path, { method: 'DELETE' }),
    action: (path: string, method: 'GET' | 'POST' = 'GET') => nothing(path, { method }),
  };
}

export const client = createClient(BASE_URL);
export const powerflowClient = createClient(POWERFLOW_BASE_URL);

export function getErrorMessage(error: unknown, fallback = 'Something went wrong'): string {
  if (error && typeof error === 'object' && 'detail' in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail === 'object' && 'message' in detail) {
      return String((detail as { message: unknown }).message);
    }
    // FastAPI validation errors: [{loc, msg, ...}, ...]
    if (Array.isArray(detail) && detail.length > 0) {
      return detail
        .map((item) => (item && typeof item === 'object' && 'msg' in item ? String(item.msg) : ''))
        .filter(Boolean)
        .join('; ');
    }
  }
  return error instanceof Error ? error.message : fallback;
}
