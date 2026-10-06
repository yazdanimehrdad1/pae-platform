// The server URL typed in Settings is normalized to backend-ot's base (no trailing slash, no /api),
// and anything that isn't an http(s) URL is rejected with a message the user can act on. In
// development the default is backend-ot on the PC the app was loaded from, never a tunnel host.
import { serverUrl, serverUrlFromDevHost, serverUrlSchema } from "@/shared/config/serverUrl";

describe("serverUrlFromDevHost", () => {
  it.each([
    ["192.168.1.23:8081", "http://192.168.1.23:8000"],
    ["192.168.1.23", "http://192.168.1.23:8000"],
    ["my-pc.local:8081", "http://my-pc.local:8000"],
    ["192.168.1.23:8081/--/some/path", "http://192.168.1.23:8000"],
    ["[fe80::1]:8081", "http://[fe80::1]:8000"],
  ])("maps %j to backend-ot on the same host", (hostUri, expected) => {
    expect(serverUrlFromDevHost(hostUri, 8000)).toBe(expected);
  });

  it("uses the given backend port", () => {
    expect(serverUrlFromDevHost("10.0.0.2:8081", 18000)).toBe("http://10.0.0.2:18000");
  });

  it.each([undefined, null, "", "abc-anonymous-8081.exp.direct", "1a2b.ngrok-free.app:80", "a:b:c"])(
    "gives null for %j",
    (hostUri) => {
      expect(serverUrlFromDevHost(hostUri, 8000)).toBeNull();
    },
  );
});

describe("serverUrlSchema", () => {
  it.each([
    ["http://192.168.1.10:8000", "http://192.168.1.10:8000"],
    ["  http://192.168.1.10:8000/  ", "http://192.168.1.10:8000"],
    ["https://ot.example.com/api", "https://ot.example.com"],
    ["https://ot.example.com/api/", "https://ot.example.com"],
  ])("normalizes %j", (input, expected) => {
    expect(serverUrlSchema.parse(input)).toBe(expected);
  });

  it.each(["192.168.1.10:8000", "ftp://host", "not a url", ""])("rejects %j", (input) => {
    expect(serverUrlSchema.safeParse(input).success).toBe(false);
  });
});

describe("serverUrl", () => {
  it("keeps a saved value across a reload", async () => {
    await serverUrl.set("http://10.0.0.5:8000");
    await serverUrl.set("http://10.0.0.6:8000");
    expect(await serverUrl.load()).toBe("http://10.0.0.6:8000");
    expect(serverUrl.get()).toBe("http://10.0.0.6:8000");
  });
});
