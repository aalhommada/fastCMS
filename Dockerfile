# ── Stage 1: Builder ──────────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy only dependency spec first (layer caching)
COPY pyproject.toml ./

# Install dependencies into a virtual env
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install core deps + PostgreSQL driver
RUN pip install --no-cache-dir . asyncpg psycopg2-binary

# ── Stage 2: Runtime ─────────────────────────────────────────────
FROM python:3.13-slim

LABEL maintainer="FastCMS Team <team@fastcms.dev>"
LABEL description="FastCMS — Open-source Backend-as-a-Service"

# Runtime deps only (Pillow needs libjpeg/libpng, psycopg needs libpq)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    libpng16-16 \
    libwebp7 \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual env from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy application code
COPY app/ ./app/
COPY cli/ ./cli/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY pyproject.toml ./

# Create directories for runtime data
RUN mkdir -p data/files data/files/thumbs hooks plugins

# Default port
EXPOSE 8000

# Health check — hits the admin login page
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/admin/login || exit 1

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
