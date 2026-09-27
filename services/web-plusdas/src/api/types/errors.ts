// Client-side error shape: FastAPI's JSON error body (with `detail`), or this fallback when the
// body isn't JSON (src/api/client.ts).
export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}
