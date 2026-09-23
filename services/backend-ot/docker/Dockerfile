# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Builder stage: create a venv and install dependencies (+ editable package)
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Isolated venv we can copy wholesale into the runtime image
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install deps from pyproject. src/ is needed because the editable install
# resolves the declared packages from it. The editable finder points at
# /app/src, which is the same path used in the runtime stage below.
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --upgrade pip setuptools wheel && \
    pip install -e .

# ---------------------------------------------------------------------------
# Runtime stage: slim, non-root, no build tooling, no tests
# ---------------------------------------------------------------------------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src

WORKDIR /app

# Non-root runtime user
RUN groupadd --system app && \
    useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app

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
