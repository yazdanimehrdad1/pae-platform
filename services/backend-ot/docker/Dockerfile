# syntax=docker/dockerfile:1

# Build context: services/backend-ot (never the monorepo root).

# ---------------------------------------------------------------------------
# Builder stage: install the locked dependencies (+ editable package) into a venv
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

# uv pinned to an exact version so image builds are reproducible.
COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first (cached layer), exactly as pinned in uv.lock; dev group excluded.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Then the project itself (editable). The editable finder points at /app/src,
# which is the same path used in the runtime stage below.
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Runtime stage: slim, non-root, no build tooling, no tests
# ---------------------------------------------------------------------------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src

WORKDIR /app

# Non-root runtime user. UID/GID pinned to 999 to match k8s runAsUser/runAsGroup.
RUN groupadd --system --gid 999 app && \
    useradd --system --uid 999 --gid app --home-dir /app --shell /usr/sbin/nologin app

# Bring in the pre-built venv (dependencies) from the builder
COPY --from=builder /opt/venv /opt/venv

# Application code only — tests/ are intentionally NOT shipped to the image
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY docker/entrypoint.sh /app/docker/entrypoint.sh

# Make entrypoint executable and normalise CRLF (in case of Windows checkout)
RUN chmod +x /app/docker/entrypoint.sh && \
    sed -i 's/\r$//' /app/docker/entrypoint.sh && \
    chown -R app:app /app

USER app

EXPOSE 8000

# Liveness only — hits the dependency-free /api/healthz (Modbus/DB/Redis issues
# won't fail it; k8s uses /api/readyz for readiness).
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/healthz')" || exit 1

# Runs migrations (unless RUN_MIGRATIONS_ON_START=false) before starting the app.
ENTRYPOINT ["/app/docker/entrypoint.sh"]

# Single uvicorn process per container. Scale horizontally via k8s replicas + HPA,
# NOT multiple workers: the scheduler runs in-process and relies on Redis leader
# election, so one process per pod keeps exactly one poller cluster-wide.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
