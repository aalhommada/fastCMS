# syntax=docker/dockerfile:1.7
# ── Stage 1: Builder ──────────────────────────────────────────────
# Use uv for dependency installation — ~10x faster than pip, deterministic.
FROM python:3.13-slim AS builder

# Install uv via its official slim image (just copies the binary)
COPY --from=ghcr.io/astral-sh/uv:0.5.9 /uv /uvx /usr/local/bin/

WORKDIR /build

# Build-time deps for any wheels that don't ship pre-built
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Dependency spec first, so layer cache survives source edits
COPY pyproject.toml ./

# Resolve + install into an isolated virtualenv. Postgres drivers are added
# explicitly because they aren't in pyproject's default deps (they're for
# the prod compose stack, not the SQLite dev path).
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
RUN uv venv /opt/venv --python 3.13
RUN uv pip install --python /opt/venv/bin/python \
    --no-cache \
    . asyncpg psycopg2-binary

# ── Stage 2: Runtime ─────────────────────────────────────────────
FROM python:3.13-slim

LABEL maintainer="FastCMS Team <team@fastcms.dev>"
LABEL description="FastCMS — Open-source Backend-as-a-Service (uv-built)"
LABEL org.opencontainers.image.source="https://github.com/aalhommada/fastCMS"
LABEL org.opencontainers.image.licenses="MIT"

# Runtime-only system libs: pillow needs libjpeg/libpng/libwebp; psycopg needs libpq
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    libpng16-16 \
    libwebp7 \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Drop the pre-built venv in
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Application source
COPY app/ ./app/
COPY cli/ ./cli/
COPY migrations/ ./migrations/
COPY alembic.ini pyproject.toml ./

# Runtime data dirs — these are typically volume-mounted in production
RUN mkdir -p data/files data/files/thumbs hooks plugins

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
