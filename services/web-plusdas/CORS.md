# CORS — What It Is and How We Handle It

## What is CORS?

CORS (Cross-Origin Resource Sharing) is a browser security rule. A request is "cross-origin" when the **protocol**, **host**, or **port** of the requester differs from the target. For example:

- Frontend: `http://localhost:8080`
- Backend: `http://localhost:8000`

Even though both are on `localhost`, different ports make them different origins. The browser will block the request unless the backend explicitly says "I allow requests from `localhost:8080`".

CORS only applies to **browsers** — tools like Postman or curl are not affected.

---

## The Problem We Hit

`VITE_RTAC_SERVER_BASE_URL` was set to `http://localhost:8000` in `.env.development`, so `client.ts` built absolute URLs like:

```
http://localhost:8000/api/sites/
```

The browser saw this as cross-origin and blocked it. The Network tab showed `0 B transferred` — the request never completed.

## The Second Cause — Trailing Slashes

Even with `VITE_RTAC_SERVER_BASE_URL` empty, the same `0 B transferred` symptom came back. The
backend routes have **no trailing slash**, and FastAPI's `redirect_slashes` answers a slashed path
with a `307` whose `Location` is an **absolute** URL:

```
GET http://localhost:8080/api/sites/     (same origin, fine so far)
→ 307, location: http://localhost:8000/api/sites
```

The browser follows that redirect to `localhost:8000` — now cross-origin — and the backend sends no
`Access-Control-Allow-Origin` header, so it is blocked. The Vite proxy does not help, because the
redirect is handed to the browser rather than followed server-side.

**Rule: never put a trailing slash on an API path in `src/api/*`.** Write `/sites`, not `/sites/`.

As a dev-only safety net, `vite.config.ts` sets `followRedirects: true` on the `/api` proxy so a
stray redirect is followed server-side. This does **not** apply to production builds behind Nginx,
so correct paths remain the real fix.

---

## Local Development

### Frontend Fix (already applied)

Keep `VITE_RTAC_SERVER_BASE_URL` empty in `.env.development` so `BASE_URL` resolves to just `/api`:

```env
VITE_RTAC_SERVER_BASE_URL=
```

This makes all API calls relative (e.g. `/api/sites/`), which go to the same origin as the frontend (`localhost:8080`) and are forwarded by the Vite dev proxy.

### The Vite Proxy

`vite.config.ts` has a proxy that intercepts any request starting with `/api` and forwards it to the real backend:

```ts
server: {
  port: 8080,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
},
```

**How it works:**

```
Browser → localhost:8080/api/sites/   (same origin, no CORS)
             ↓ Vite proxy (server-side)
Backend ← localhost:8000/api/sites/   (server-to-server, no CORS)
```

The browser never makes a cross-origin request — Vite handles the forwarding on the server side.

> This proxy only works during `npm run dev`. It is NOT available in production builds.

---

## Production

In production the Vite proxy is gone. You have two options:

### Option A — Nginx Reverse Proxy (Recommended)

Serve both the frontend and the backend under the same domain using Nginx. The browser only ever talks to one origin, so there is no CORS at all.

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Serve the built frontend
    location / {
        root /var/www/pae-plusdas/dist;
        try_files $uri $uri/ /index.html;
    }

    # Forward /api calls to the backend
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

With this setup, `VITE_RTAC_SERVER_BASE_URL` stays empty in `.env.production` — the same relative `/api` approach works in both dev and prod.

```env
# .env.production
VITE_RTAC_SERVER_BASE_URL=
```

Build the frontend for production:
```bash
npm run build
```

### Option B — Backend CORS Headers (if no reverse proxy)

If the frontend and backend are on different domains/ports with no reverse proxy in front, set `VITE_RTAC_SERVER_BASE_URL` to the backend's public URL in `.env.production`:

```env
# .env.production
VITE_RTAC_SERVER_BASE_URL=https://api.yourdomain.com
```

Then configure CORS on the backend to allow the frontend's production origin.

#### FastAPI
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",           # local dev
        "https://yourdomain.com",          # production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### Express (Node)
```js
const cors = require('cors');
app.use(cors({
  origin: ['http://localhost:8080', 'https://yourdomain.com'],
}));
```

#### Django
```python
# settings.py
INSTALLED_APPS += ['corsheaders']
MIDDLEWARE = ['corsheaders.middleware.CorsMiddleware', ...rest]
CORS_ALLOWED_ORIGINS = [
    'http://localhost:8080',
    'https://yourdomain.com',
]
```

---

## Summary Checklist

| Context | Frontend (`VITE_RTAC_SERVER_BASE_URL`) | Backend |
|---|---|---|
| Local dev (`npm run dev`) | Empty — Vite proxy handles it | No CORS config needed |
| Production with Nginx reverse proxy | Empty — Nginx handles forwarding | No CORS config needed |
| Production without reverse proxy | Set to backend public URL | Add CORS middleware with frontend origin |
| Docker (same host, different ports) | Empty if Nginx in front, otherwise set URL | Add CORS middleware |
| Adding a new backend service | Leave empty | Add the new `/api/new-service` route to Nginx or Vite proxy |
