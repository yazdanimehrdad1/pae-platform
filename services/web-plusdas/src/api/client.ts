import type { ApiError } from '@/shared/types/api';
import { getRuntimeConfig } from '@/shared/config/runtime';

// Same-origin API base from runtime config (default `/api`), never a build-time value.
export const BASE_URL = getRuntimeConfig().apiBaseUrl;

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
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

  return response.json();
}

async function requestVoid(path: string, init?: RequestInit): Promise<void> {
  const response = await fetch(`${BASE_URL}${path}`, {
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
}

export const client = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (path: string) => requestVoid(path, { method: 'DELETE' }),
  action: (path: string, method: 'GET' | 'POST' = 'GET') => requestVoid(path, { method }),
};

export function getErrorMessage(error: unknown, fallback = 'Something went wrong'): string {
  if (error && typeof error === 'object' && 'detail' in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail === 'object' && 'message' in detail) {
      return String((detail as { message: unknown }).message);
    }
  }
  return error instanceof Error ? error.message : fallback;
}
