// Integration check for a RUNNING web-plusdas container: the SPA is served with the right
// cache headers, /api reaches backend-ot, /powerflow-api powerflow and /intelli-gateway-api
// intelli-gateway on the same origin, and /api and /powerflow-api need a login (nginx auth_request).
// Node stdlib only (fetch).
//
// Usage: node scripts/check_same_origin.mjs [--url http://localhost:5173]
// Run by `make test-integration`. Needs the root dev stack (`make up` at the repo root) or a
// standalone `make up` here with backend-ot reachable.

const urlFlag = process.argv.indexOf("--url");
const baseUrl = (urlFlag > -1 ? process.argv[urlFlag + 1] : "http://localhost:5173").replace(/\/$/, "");

const failures = [];
const check = (name, passed, detail = "") => {
  console.log(`${passed ? "ok  " : "FAIL"} ${name}${detail ? ` (${detail})` : ""}`);
  if (!passed) failures.push(name);
};

async function get(path, cookie) {
  const headers = cookie ? { cookie } : {};
  const response = await fetch(`${baseUrl}${path}`, { redirect: "manual", headers });
  return { response, body: await response.text() };
}

// The dev stack's demo login (demo@plusdas.local, created by make up), or CHECK_EMAIL / CHECK_PASSWORD.
const LOGIN = {
  email: process.env.CHECK_EMAIL ?? "demo@plusdas.local",
  password: process.env.CHECK_PASSWORD ?? "demo-password",
};

/** The session cookie ("name=value"), or null when that login doesn't exist here. */
async function login() {
  const response = await fetch(`${baseUrl}/intelli-gateway-api/v1/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(LOGIN),
  });
  await response.text();
  if (response.status !== 200) return null;
  return response.headers.get("set-cookie")?.split(";")[0] ?? null;
}

async function main() {
  try {
    await get("/");
  } catch {
    console.error(`check_same_origin: nothing answers on ${baseUrl}; start the dev stack first (make up)`);
    return 2;
  }

  const root = await get("/");
  check("/ serves the app shell", root.response.status === 200 && root.body.includes('<div id="root">'));
  check("/ is not cached", root.response.headers.get("cache-control") === "no-cache",
    root.response.headers.get("cache-control") ?? "no header");
  check("index.html loads /config.js", root.body.includes('src="/config.js"'));

  const deepRoute = await get("/sites/manage");
  check("client-side route falls back to index.html",
    deepRoute.response.status === 200 && deepRoute.body.includes('<div id="root">'));

  const config = await get("/config.js");
  check("/config.js sets window.__APP_CONFIG__", config.body.includes("window.__APP_CONFIG__"));
  check("/config.js is never cached", config.response.headers.get("cache-control") === "no-store",
    config.response.headers.get("cache-control") ?? "no header");

  const assetPath = root.body.match(/\/assets\/[^"']+\.js/)?.[0];
  if (assetPath) {
    const asset = await get(assetPath);
    check(`${assetPath} is cached immutably`,
      (asset.response.headers.get("cache-control") ?? "").includes("immutable"));
  } else {
    check("index.html references a hashed /assets/*.js bundle", false);
  }

  // Health and readiness stay open: the deploy checks /api/readyz through this origin.
  for (const openPath of ["/api/healthz", "/api/readyz"]) {
    const health = await get(openPath);
    const healthJson = (health.response.headers.get("content-type") ?? "").includes("application/json");
    check(`${openPath} reaches backend-ot through ${baseUrl} without a login`,
      health.response.status === 200 && healthJson, `status ${health.response.status}`);
  }

  // Everything else on /api and /powerflow-api needs a session (nginx asks intelli-gateway).
  for (const apiPath of ["/api/sites", "/powerflow-api/sites"]) {
    const anonymous = await get(apiPath);
    check(`${apiPath} without a session is 401`, anonymous.response.status === 401,
      `status ${anonymous.response.status}`);
  }
  const cookie = await login();
  if (cookie) {
    const sites = await get("/api/sites", cookie);
    const sitesJson = (sites.response.headers.get("content-type") ?? "").includes("application/json");
    check(`/api/sites reaches backend-ot through ${baseUrl} when logged in`,
      sites.response.status === 200 && sitesJson, `status ${sites.response.status}`);
  } else {
    console.log(`skip logged-in checks: no login ${LOGIN.email} (the gateway creates it at startup: DEMO_USER_PASSWORD)`);
  }

  const powerflow = await get("/powerflow-api/health");
  const powerflowJson = (powerflow.response.headers.get("content-type") ?? "").includes("application/json");
  check(`/powerflow-api/health reaches powerflow through ${baseUrl}`,
    powerflow.response.status === 200 && powerflowJson, `status ${powerflow.response.status}`);

  const gateway = await get("/intelli-gateway-api/healthz");
  const gatewayJson = (gateway.response.headers.get("content-type") ?? "").includes("application/json");
  check(`/intelli-gateway-api/healthz reaches intelli-gateway through ${baseUrl}`,
    gateway.response.status === 200 && gatewayJson, `status ${gateway.response.status}`);

  console.log(failures.length ? `RESULT: ${failures.length} check(s) failed` : "RESULT: same-origin OK");
  return failures.length ? 1 : 0;
}

// Set exitCode and let Node exit on its own: process.exit() while fetch's keep-alive sockets
// are still closing crashes Node on Windows (libuv assertion in src/win/async.c).
process.exitCode = await main();
