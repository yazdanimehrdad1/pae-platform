# syntax=docker/dockerfile:1
# Build context: services/powerflow (never the monorepo root).

# ---------------------------------------------------------------------------
# Builder: install the locked runtime dependencies into a venv
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

# uv pinned to an exact version so image builds are reproducible.
COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /bin/uv

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Runtime: slim, non-root, no build tooling, no tests
# ---------------------------------------------------------------------------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src

WORKDIR /app

RUN groupadd --system --gid 999 app && \
    useradd --system --uid 999 --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv
COPY src/ ./src/
# The profile scenario CSVs (sites live only in the database). compose mounts a named volume on
# profiles/, which Docker seeds from here on first use.
COPY --chown=app:app profiles/ ./profiles/
# The PAE point standard: the Modbus server's register layout and point list.
COPY docs/point-standard/ ./docs/point-standard/

USER app

EXPOSE 8000 502

# Liveness: /api/health answers once the site config has loaded.
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uvicorn", "powerflow.app:app", "--host", "0.0.0.0", "--port", "8000"]
