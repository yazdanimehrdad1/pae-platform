// apiFetch talks to the configured server and turns every failure into an ApiError the screens can
// show: backend-ot's {detail: {message}} and {detail: "..."}, HTTP status alone, and no connection.
import { ApiError, apiFetch } from "@/api/client";
import { serverUrl } from "@/shared/config/serverUrl";

const fetchMock = jest.fn();

beforeEach(async () => {
  fetchMock.mockReset();
  global.fetch = fetchMock as unknown as typeof fetch;
  await serverUrl.set("http://ot.test:8000");
});

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    json: async () => body,
  } as Response;
}

describe("apiFetch", () => {
  it("calls the configured server and returns the body", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, [{ site_id: 1001 }]));
    await expect(apiFetch("/api/sites")).resolves.toEqual([{ site_id: 1001 }]);
    expect(fetchMock.mock.calls[0][0]).toBe("http://ot.test:8000/api/sites");
  });

  it("sends a JSON body with its content type", async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}));
    await apiFetch("/api/push-devices", { method: "PUT", body: { site_ids: [1] } });
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("PUT");
    expect(init.body).toBe('{"site_ids":[1]}');
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("uses backend-ot's structured error message", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(404, { detail: { error: "NotFoundError", message: "Sites not found: 9" } }),
    );
    await expect(apiFetch("/api/x")).rejects.toEqual(new ApiError(404, "Sites not found: 9"));
  });

  it("uses a plain string detail", async () => {
    fetchMock.mockResolvedValue(jsonResponse(422, { detail: "start_time needs a UTC offset" }));
    await expect(apiFetch("/api/x")).rejects.toMatchObject({ status: 422, message: "start_time needs a UTC offset" });
  });

  it("falls back to the HTTP status", async () => {
    fetchMock.mockResolvedValue(jsonResponse(500, null));
    await expect(apiFetch("/api/x")).rejects.toMatchObject({ status: 500, message: "500 Error" });
  });

  it("reports an unreachable server as status 0 with the URL", async () => {
    fetchMock.mockRejectedValue(new TypeError("Network request failed"));
    await expect(apiFetch("/api/x")).rejects.toMatchObject({
      status: 0,
      message: "Can't reach http://ot.test:8000 (Network request failed)",
    });
  });
});
