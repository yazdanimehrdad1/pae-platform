// Client-side error shape: FastAPI's JSON error body (with `detail`), or this fallback when the
// body isn't JSON (src/api/client.ts). `status` is the HTTP status, added by the client.
export interface ApiError {
  code: string;
  message: string;
  status?: number;
  details?: Record<string, unknown>;
}
