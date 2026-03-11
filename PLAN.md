# FastCMS — Project Plan

## What Is FastCMS

FastCMS is an **open-source Backend-as-a-Service (BaaS)** built with FastAPI + Python. Think PocketBase/Supabase but Python-native. The core is lightweight — AI and advanced features are optional plugins.

**Repos:**
- `fastCMS/` — Core app (this repo)
- `fastcms-plugins/` — Official plugin collection (separate repo: `github.com/aalhommada/fastcms-plugins`)
- `fastcms-docs/` — Documentation site (separate repo)

---

## Tech Stack

- **Framework:** FastAPI 0.115, Python 3.13
- **DB:** SQLAlchemy 2.0 async + Alembic migrations, SQLite default (PostgreSQL supported)
- **Auth:** JWT (python-jose) + bcrypt (passlib), 2FA/TOTP, OAuth (Google/GitHub/Microsoft), OTP passwordless
- **Admin UI:** Jinja2 templates + Tailwind CSS + Alpine.js at `/admin`
- **Real-time:** WebSockets + SSE
- **Storage:** Local / S3 / Azure Blob (pluggable)
- **Scheduling:** APScheduler + croniter
- **SDKs:** TypeScript (`sdk/typescript/`) + Python (`sdk/python/`)
- **Plugins:** Drop-in Python packages in `plugins/` directory

---

## What Has Been Done (Complete)

### Phase 1 — Auth Completeness
- [x] Account lockout after N failed logins
- [x] Password policies (min length, uppercase, lowercase, digit, special)
- [x] Email change flow (`/request-email-change`, `/confirm-email-change`)
- [x] OTP passwordless login (`/request-otp`, `/auth-with-otp`)
- [x] 2FA/TOTP with backup codes
- [x] API keys for service auth (X-API-Key header)
- [x] User impersonation (admin)
- [x] Session management (list/revoke)

### Phase 2 — File System
- [x] On-demand image thumbnails (`?thumb=WxH[fbt]` — crop, fit, top, bottom, proportional)
- [x] Protected files with short-lived JWT tokens
- [x] File upload/download/list/delete

### Phase 3 — Collection & API
- [x] AutodateField (auto-set timestamp on create/update)
- [x] `:changed` modifier in access rules
- [x] `manage_rule` on collections
- [x] Collection truncate endpoint
- [x] Batch operations (createMany, upsertMany, deleteMany)
- [x] CSV import/export
- [x] Full-text search (FTS5)

### Phase 4 — Security & Extensibility
- [x] Security headers middleware (CSP, HSTS, X-Frame-Options, etc.)
- [x] Enhanced audit logging
- [x] Per-user/IP rate limiting with role-based limits
- [x] Server-side Python hooks (`hooks/` directory, auto-loaded)
- [x] IP allowlist/blocklist middleware
- [x] Prometheus metrics
- [x] Admin cron management UI
- [x] Async email service with security notifications

### Phase 5 — SDKs
- [x] TypeScript SDK — auth, collections, files, batch, realtime (SSE with auto-reconnect)
- [x] Python SDK — sync + async clients, full auth, collections, files, realtime
- [x] Both published as packages (`fastcms-sdk`)

### Phase 6 — Tests
- [x] 204 tests total (138 core + 66 plugin tests)
- [x] Unit tests for autodate, changed modifier, image transforms, metrics, SDKs
- [x] Plugin tests for ai_core, ai_vectors, ai_rag, ai_agents
- [x] E2E tests for plugin system

### Phase 7 — Plugin System & AI (Latest)
- [x] Plugin architecture — `PluginContext` API (include_router, on_record_*, add_admin_page, get_setting)
- [x] Plugin loader with `fastcms_plugin` namespace for cross-plugin imports
- [x] Plugin settings DB table + admin CRUD
- [x] Dynamic sidebar — plugins register admin pages, base.html renders them
- [x] AI removed from core, reimplemented as 4 optional plugins:
  - `ai_core` — Provider abstraction (OpenAI, Anthropic, Ollama, LM Studio, vLLM — any OpenAI-compatible)
  - `ai_vectors` — Embedding storage + semantic search (separate SQLite DB, numpy optional)
  - `ai_rag` — RAG pipeline (chunk → embed → store → retrieve → answer)
  - `ai_agents` — Autonomous agents with 7 tools (list/query/get/create/update/search/semantic_search)
- [x] AI Playground admin page (Configure, Chat, RAG, Agents tabs)
- [x] Plugin docs in fastcms-docs
- [x] Separate fastcms-plugins repo
- [x] Tested live with LM Studio (qwen3-coder-30b + nomic-embed-text)

### Admin UI Pages (All Working)
- [x] Dashboard, Users, Collections, Records, Files
- [x] API Reference, Auth Docs
- [x] Sessions, IP Rules, Metrics
- [x] Webhooks, Hooks, Plugins, Backups, Cron
- [x] Settings, Email Settings, Profile
- [x] Realtime (WebSocket)
- [x] AI Playground (dynamic, from plugin)

---

## What Needs To Be Done Next

### Priority 1 — Production Readiness

#### ~~1.1 Persist AI Plugin Configuration~~ DONE
AI provider config is now saved to `plugin_settings` DB table on configure and auto-loaded on startup via `ctx.get_setting()`. All 8 settings persisted (provider, api_key, base_url, model, embed_provider, embed_api_key, embed_base_url, embed_model).

#### ~~1.2 Docker & Docker Compose~~ DONE
Production deployment setup. Multi-stage Dockerfile (python:3.13-slim, ~150MB final image), docker-compose.yml with PostgreSQL 17, docker-compose.dev.yml with SQLite + hot reload, .dockerignore, health checks, volume mounts for data/plugins/hooks.

#### 1.3 PostgreSQL Production Testing
SQLite is great for dev but PostgreSQL needed for production.
- Run full test suite against PostgreSQL
- Fix any SQLite-specific SQL (FTS5, JSON functions)
- Connection pooling config
- **Effort:** Medium

#### 1.4 Environment & Security Hardening
- [ ] Secret rotation support
- [ ] CORS configuration (currently permissive)
- [ ] Remove debug mode protections (Swagger UI in production)
- [ ] Secure cookie settings (HttpOnly, Secure, SameSite=Strict)
- [ ] Rate limit config tuning for production
- **Effort:** Small-Medium

### Priority 2 — Missing Features for Competitive Parity

#### 2.1 File Upload in RAG Plugin
Currently RAG only accepts text. Should support:
- PDF upload + text extraction
- Markdown/HTML parsing
- File upload endpoint that auto-ingests
- **Files:** `plugins/ai_rag/routes.py`, new `plugins/ai_rag/extractors.py`
- **Effort:** Medium

#### 2.2 OAuth Enhancements
- [ ] PKCE support for mobile/SPA clients
- [ ] More providers (Apple, Discord, LinkedIn)
- [ ] Custom OAuth provider configuration via admin UI
- **Effort:** Medium

#### 2.3 Webhook Improvements
- [ ] Signed webhook payloads (HMAC-SHA256)
- [ ] Retry with exponential backoff
- [ ] Delivery status tracking and logs
- **Effort:** Medium

#### 2.4 Field-Level Encryption
- Encrypt sensitive fields at rest
- Key rotation support
- Transparent decrypt on read
- **Effort:** Large

#### 2.5 Compliance Features
- GDPR data export (user's own data)
- Right to deletion
- Data retention policies
- Consent management
- **Effort:** Large

### Priority 3 — Developer Experience

#### 3.1 CLI Improvements
- `fastcms init` — project scaffolding (already exists, needs polish)
- `fastcms plugin install <name>` — install from fastcms-plugins repo
- `fastcms plugin create <name>` — scaffold a new plugin
- `fastcms migrate` — run Alembic migrations
- `fastcms seed` — seed demo data
- **Effort:** Medium

#### 3.2 SDK Publishing
- Publish TypeScript SDK to npm (`@fastcms/sdk`)
- Publish Python SDK to PyPI (`fastcms-sdk`)
- Automated publishing via GitHub Actions
- **Effort:** Medium

#### 3.3 Documentation Site
- Complete API reference docs
- Getting started guide
- Plugin development guide
- Deployment guide (Docker, Railway, Fly.io, VPS)
- **Effort:** Large

#### 3.4 Admin UI Polish
- [ ] Dark mode
- [ ] Record relations visualization
- [ ] Collection schema builder (drag & drop fields)
- [ ] API explorer (built-in, not just Swagger)
- [ ] Plugin marketplace page (browse/install from fastcms-plugins)
- **Effort:** Large

### Priority 4 — AI Plugin Enhancements

#### 4.1 Conversation Memory
- Store chat history per user/session
- Multi-turn conversations with context
- **Files:** New `plugins/ai_chat/` plugin or extend `ai_core`
- **Effort:** Medium

#### 4.2 RAG Improvements
- PDF/DOCX file upload support
- Chunking strategy configuration (size, overlap, method)
- Collection-aware RAG (auto-ingest when records are created)
- Hybrid search (FTS5 + semantic)
- **Effort:** Medium-Large

#### 4.3 Agent Improvements
- Custom tool definitions via admin UI
- Agent memory/state persistence
- Multi-agent workflows
- Webhook-triggered agents
- **Effort:** Large

#### 4.4 More AI Providers
- Google Gemini
- AWS Bedrock
- Azure OpenAI
- Groq, Together.ai, Fireworks
- **Effort:** Small per provider (same OpenAI-compatible pattern)

#### 4.5 AI Admin Dashboard
- Usage stats (tokens, requests, costs)
- Provider health monitoring
- Model comparison testing
- **Effort:** Medium

### Priority 5 — Scaling & Infrastructure

#### 5.1 Redis Integration
- Distributed rate limiting
- Session storage
- Pub/sub for multi-instance realtime
- Cache layer
- **Effort:** Medium

#### 5.2 Background Job Queue
- Replace APScheduler with Celery or ARQ for production
- Job status tracking
- Retry policies
- **Effort:** Medium

#### 5.3 Multi-Tenancy
- Workspace/organization support
- Per-tenant databases or schema isolation
- Tenant-scoped API keys
- **Effort:** Very Large

---

## Architecture Decisions

### Core Principles
1. **Lightweight core** — No AI deps, no heavy libraries in core. Everything optional via plugins.
2. **SQLite-first** — Works out of the box, PostgreSQL for production scale.
3. **Plugin everything** — Features beyond CRUD/auth/files should be plugins.
4. **OpenAI-compatible** — AI plugins work with any OpenAI-compatible API (LM Studio, vLLM, Ollama, cloud APIs).
5. **No vendor lock-in** — Switch providers, databases, storage backends without code changes.

### Plugin Architecture
```
plugins/
  my_plugin/
    __init__.py    # PLUGIN_META dict + register(ctx: PluginContext)
    routes.py      # FastAPI router (mounted at /api/v1/plugins/...)
    models.py      # SQLAlchemy models (optional)
    hooks.py       # Event handlers (optional)
    templates/     # Jinja2 templates (optional)
```

**PluginContext API:**
- `ctx.include_router(router, prefix=...)` — Register API routes
- `ctx.on_record_create(collection, handler)` — Hook into record events
- `ctx.add_admin_page(nav_id, label, icon, url)` — Add sidebar link
- `ctx.get_setting(key, default)` — Read plugin settings from DB

**Cross-plugin imports:** `from fastcms_plugin.ai_core.providers import get_provider`

### Key File Locations
```
app/main.py                    — Entry point, middleware, lifespan
app/core/config.py             — Settings (pydantic-settings, .env)
app/core/plugin_loader.py      — Plugin discovery and loading
app/core/plugin_registry.py    — Plugin metadata + admin pages registry
app/fastcms_plugin_api.py      — PluginContext class
app/api/v1/                    — REST API endpoints
app/services/                  — Business logic layer
app/db/models/                 — SQLAlchemy models
app/db/session.py              — Database session factory
app/admin/routes.py            — Admin UI routes
app/admin/templates/           — Jinja2 admin templates
plugins/                       — Plugin packages (auto-loaded)
hooks/                         — Drop-in hook scripts (auto-loaded)
sdk/typescript/                — TypeScript SDK
sdk/python/                    — Python SDK
tests/                         — Unit, integration, e2e tests
migrations/                    — Alembic migrations
```

### Running
```bash
# Development
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Tests
.venv/bin/python -m pytest tests/unit/ --ignore=tests/unit/test_field_types.py -q

# Admin panel
http://localhost:8000/admin  (admin@fastcms.dev / AdminPass123!)

# API docs
http://localhost:8000/docs
```

---

## Known Issues
- `tests/unit/test_field_types.py` — 20 pre-existing test failures (RelationOptions schema mismatch). Not related to recent work.
- AI plugin config is runtime-only — needs persistence to `plugin_settings` table.
- Admin UI uses Tailwind CDN — should be bundled for production.
- Rate limiter uses in-memory storage — needs Redis for multi-instance.
