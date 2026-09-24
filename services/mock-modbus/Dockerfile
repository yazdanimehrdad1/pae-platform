# syntax=docker/dockerfile:1
# DEV-ONLY image. Build context: services/mock-modbus (never the monorepo root).

# ---------------------------------------------------------------------------
# Builder: install the locked runtime dependencies into a venv
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

# uv pinned to an exact version so image builds are reproducible.
COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /bin/uv

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /opt/mock-modbus
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN groupadd --gid 1000 modbus && \
    useradd --uid 1000 --gid modbus --create-home modbus

WORKDIR /opt/mock-modbus

COPY --from=builder /opt/venv /opt/venv
COPY app/ app/

RUN chown -R modbus:modbus /opt/mock-modbus

USER modbus

EXPOSE 502

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1',502)); s.close()"

CMD ["python", "-m", "app.server"]
