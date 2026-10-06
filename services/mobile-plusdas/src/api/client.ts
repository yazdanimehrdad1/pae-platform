import { serverUrl } from "@/shared/config/serverUrl";

const TIMEOUT_MS = 10_000;

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** backend-ot errors: `detail` is {error, message} for app errors, a string otherwise. */
function errorMessage(body: unknown, fallback: string): string {
  if (typeof body !== "object" || body === null || !("detail" in body)) return fallback;
  const { detail } = body as { detail: unknown };
  if (typeof detail === "string") return detail;
  if (typeof detail === "object" && detail !== null && "message" in detail) {
    return String((detail as { message: unknown }).message);
  }
  return fallback;
}

/** Call backend-ot at the configured server URL. `path` starts with /api. */
export async function apiFetch<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${serverUrl.get()}${path}`, {
      method: init.method ?? "GET",
      headers: {
        Accept: "application/json",
        ...(init.body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
      signal: controller.signal,
    });
  } catch (error) {
    const reason = controller.signal.aborted ? "timed out" : error instanceof Error ? error.message : "failed";
    throw new ApiError(0, `Can't reach ${serverUrl.get()} (${reason})`);
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    throw new ApiError(response.status, errorMessage(body, `${response.status} ${response.statusText}`));
  }
  return (await response.json()) as T;
}
