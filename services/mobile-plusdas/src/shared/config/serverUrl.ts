import Constants from "expo-constants";
import { z } from "zod";

import { persistedValue } from "@/shared/lib/persistedValue";

// The backend-ot base URL (no trailing slash, no /api). Chosen at runtime in Settings, so one
// build works against any environment; the build only supplies the first value.
export const serverUrlSchema = z
  .string()
  .trim()
  .url("Enter a full URL, e.g. http://192.168.1.10:8000")
  .refine((url) => /^https?:\/\//i.test(url), "Use http:// or https://")
  .transform((url) => url.replace(/\/+$/, "").replace(/\/api$/i, ""));

/**
 * In development the app is loaded from Metro on the developer's PC (`hostUri`, e.g.
 * "192.168.1.23:8081"), and backend-ot runs on that same PC: same host, backend-ot's port.
 * Null when there is no dev server, or when Metro is reached through a tunnel (a public host
 * that doesn't lead to backend-ot).
 */
export function serverUrlFromDevHost(hostUri: string | null | undefined, port: number): string | null {
  if (!hostUri) return null;
  const authority = hostUri.split("/")[0] ?? "";
  const match = /^(\[[^\]]+\]|[^:[\]]+)(?::\d+)?$/.exec(authority);
  const host = match?.[1];
  if (!host || /(\.exp\.direct|ngrok[\w-]*\.(app|io|dev))$/i.test(host)) return null;
  return `http://${host}:${port}`;
}

const extra = Constants.expoConfig?.extra;
const backendPort = typeof extra?.backendPort === "number" ? extra.backendPort : 8000;

/** The PC this dev session runs on, when there is one. */
export const DETECTED_SERVER_URL = serverUrlFromDevHost(Constants.expoConfig?.hostUri, backendPort);

export const DEFAULT_SERVER_URL =
  DETECTED_SERVER_URL ??
  (typeof extra?.defaultServerUrl === "string" ? extra.defaultServerUrl : "http://localhost:8000");

/** A URL saved in Settings wins over the default; "Use detected" in Settings goes back to it. */
export const serverUrl = persistedValue<string>("plusdas.serverUrl", DEFAULT_SERVER_URL);
