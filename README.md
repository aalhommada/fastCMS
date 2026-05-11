# FastCMS

> The **AI-native** Python BaaS — RAG, vector search, and autonomous
> agents on top of auth, real-time, files, and dynamic collections.
> Modular by design: AI extensions plug in, never bloat the install.

[![PyPI](https://img.shields.io/pypi/v/pyfastcms.svg)](https://pypi.org/project/pyfastcms/)
[![Python](https://img.shields.io/pypi/pyversions/pyfastcms.svg)](https://pypi.org/project/pyfastcms/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

FastCMS gives your frontend a complete backend in minutes — dynamic
schemas, JWT auth, real-time WebSocket subscriptions, file storage with
thumbnails, webhooks, and an admin dashboard. Build on top of FastAPI +
SQLAlchemy. Drop in plugins when you need AI, custom fields, or
integrations.

---

## Install

FastCMS uses [**uv**](https://github.com/astral-sh/uv) — the fast modern
Python toolchain from Astral — as its recommended installer. uv handles
Python versions, virtualenvs, and packages with one command, and is
~10× faster than `pip` on every operation.

### Prerequisites

```bash
# Install uv (one-time, takes ~5s)
curl -LsSf https://astral.sh/uv/install.sh | sh         # macOS / Linux
# Windows (PowerShell):
#   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Recommended — `uv tool install` (treats `fastcms` like a global CLI)

```bash
uv tool install pyfastcms
fastcms init my-app
cd my-app
fastcms dev
```

No venv to manage — uv isolates the install. Admin at
<http://localhost:8000/admin>, OpenAPI playground at
<http://localhost:8000/docs>.

### Project-local — `uv add` inside your own app

```bash
uv init my-app
cd my-app
uv add pyfastcms
uv run fastcms dev
```

### Docker (multi-service: FastCMS + Postgres + Redis)

```bash
git clone https://github.com/aalhommada/fastCMS && cd fastCMS
cp .env.example .env       # set SECRET_KEY (openssl rand -hex 32) inside
docker compose up -d
```

Production-grade stack with Postgres + Redis. See the full
[deployment guide](https://fastcms.org/docs/deployment/docker).

### With cloud storage backends

```bash
uv tool install 'pyfastcms[s3]'        # AWS S3 / MinIO / DigitalOcean Spaces
uv tool install 'pyfastcms[azure]'     # Azure Blob
uv tool install 'pyfastcms[storage]'   # both at once
```

### From source (for contributors)

```bash
git clone https://github.com/aalhommada/fastCMS && cd fastCMS
uv sync --all-extras       # creates .venv, installs everything incl. dev tools
source .venv/bin/activate
cp .env.example .env       # set SECRET_KEY
fastcms dev
```

### Already prefer pip?

uv is recommended but not required. `pip` works too — just make sure you're
in a virtualenv (`python -m venv .venv && source .venv/bin/activate`)
before running `pip install pyfastcms`.

---

## Quick start

After `fastcms dev` is running:

### 1. Create your first user

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "you@example.com",
    "password": "YourPassword123!",
    "password_confirm": "YourPassword123!",
    "name": "Your Name"
  }'
```

The response includes an `access_token`. Save it as `TOKEN` for the next
calls. To make the user an admin:

```bash
sqlite3 data/app.db "UPDATE users SET role='admin' WHERE email='you@example.com';"
```

### 2. Create a collection

```bash
curl -X POST http://localhost:8000/api/v1/collections \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "posts",
    "type": "base",
    "schema": [
      {"name": "title",     "type": "text",   "validation": {"required": true}},
      {"name": "content",   "type": "editor"},
      {"name": "published", "type": "bool"}
    ]
  }'
```

FastCMS auto-creates the table, REST endpoints, and admin UI for it.

### 3. Add a record

```bash
curl -X POST http://localhost:8000/api/v1/collections/posts/records \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"data": {"title": "Hello", "content": "World", "published": true}}'
```

### 4. Query

```bash
# filter
curl "http://localhost:8000/api/v1/collections/posts/records?filter=published=true" \
  -H "Authorization: Bearer $TOKEN"

# full-text search
curl "http://localhost:8000/api/v1/collections/posts/records?search=hello" \
  -H "Authorization: Bearer $TOKEN"

# sort newest first
curl "http://localhost:8000/api/v1/collections/posts/records?sort=-created" \
  -H "Authorization: Bearer $TOKEN"
```

See [fastcms.org](https://fastcms.org/docs/core-concepts/records) for
the full filter operator list (`=`, `!=`, `>`, `>=`, `<`, `<=`, `~`,
`?=`), date macros (`@today`, `@day-7`), expansion, and pagination.

---

## AI plugins (RAG, vectors, agents) + extensions

FastCMS is **AI-native** but doesn't bundle AI into the core wheel.
RAG, vector search, autonomous agents, and any other extension plug
in via the `fastcms plugin install` CLI — your dependency tree stays
small, and you only ship what you actually use. The roadmap goes
deeper on agent orchestration and retrieval pipelines, all delivered
as opt-in plugins.

```bash
fastcms plugin list                 # see installed + available plugins
fastcms plugin install ai-core      # LLM provider abstraction (OpenAI, Anthropic, Ollama)
fastcms plugin install ai-vectors   # embedding storage + semantic search
fastcms plugin install ai-rag       # retrieval-augmented Q&A on your docs
fastcms plugin install ai-agents    # autonomous agents with tool calling
fastcms plugin install example      # reference plugin showing routes, hooks, admin UI
```

The CLI fetches each plugin from the official
[fastcms-plugins](https://github.com/aalhommada/fastcms-plugins)
registry, resolves dependencies, and drops it into your project's
`plugins/` directory. Restart `fastcms dev` after installing — plugins
load once at server start.

For AI: configure a provider via the admin UI at `/admin/ai` or
`POST /api/v1/plugins/ai/configure`. No API key required if you run
[Ollama](https://ollama.ai) locally.

Build your own plugin: see the [plugin development guide](https://fastcms.org/docs/plugins/plugin-development).

---

## Core features

Every feature below ships in the `pyfastcms` wheel — no plugin needed.

| Feature | Highlights |
|---|---|
| **Dynamic Collections** | Define schema via API; auto-creates table + REST endpoints + admin UI |
| **Auth Collections** | Multiple user pools (customers, vendors, admins) with JWT + bcrypt |
| **View Collections** | Virtual collections backed by SQL queries (joins, aggregations) |
| **Authentication** | JWT + refresh tokens, OAuth (Google/GitHub/Microsoft), 2FA/TOTP, API keys, magic links |
| **Real-time** | WebSocket subscriptions per-collection, presence, Redis pub/sub for multi-server |
| **File storage** | Local / S3 / Azure Blob with automatic image thumbnails (3 sizes) |
| **Access control** | Per-collection rule expressions for read/create/update/delete |
| **Hooks** | Drop a `.py` file in `hooks/` to react to record events |
| **Webhooks** | HMAC-signed delivery, exponential backoff, full retry/audit log |
| **Backup & restore** | One-click DB snapshots via API or admin |
| **CSV import/export** | Move data between environments |
| **Admin dashboard** | Web UI for everything — collections, records, users, files, settings |
| **CLI** | `fastcms init`, `fastcms dev`, `fastcms collections`, `fastcms users`, `fastcms plugin` |

---

## Configuration

Settings come from environment variables (or a `.env` file). The most
common ones:

```bash
SECRET_KEY=...                    # required — generate with: openssl rand -hex 32
DATABASE_URL=sqlite+aiosqlite:///./data/app.db
                                  # or: postgresql+asyncpg://user:pass@host/db
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 1 day default
CORS_ORIGINS=http://localhost:3000,https://yourapp.com
STORAGE_TYPE=local                # local | s3 | azure
REDIS_ENABLED=false               # set true for multi-server real-time
```

See [`.env.example`](.env.example) for the full list including OAuth,
SMTP, S3, and Azure settings.

---

## Production checklist

- [ ] Strong `SECRET_KEY` (32+ random bytes)
- [ ] `DEBUG=false` and `ENVIRONMENT=production`
- [ ] Postgres instead of SQLite (set `DATABASE_URL`)
- [ ] Redis enabled if running multiple instances (`REDIS_ENABLED=true`)
- [ ] Specific `CORS_ORIGINS` (not `*`)
- [ ] Cloud storage if you serve uploads at scale (`STORAGE_TYPE=s3`)
- [ ] Reverse proxy with TLS (the included `docker-compose.yml` is a
      good starting point)

---

## Documentation

Full docs: <https://fastcms.org>

Highlights:
- [Getting started](https://fastcms.org/docs/getting-started)
- [Collections, records, fields](https://fastcms.org/docs/core-concepts/collections)
- [Real-time](https://fastcms.org/docs/realtime/overview)
- [Webhooks](https://fastcms.org/docs/realtime/webhooks)
- [Hooks](https://fastcms.org/docs/advanced/hooks)
- [AI plugins](https://fastcms.org/docs/plugins/overview)
- [Plugin development](https://fastcms.org/docs/plugins/plugin-development)

---

## Common questions

**Where is my data stored?** SQLite at `data/app.db` by default. Switch
to Postgres in production via `DATABASE_URL`.

**Do I need AI?** No — the core works without any plugin. Install AI
plugins only if you want them.

**Can I add my own field types or endpoints?** Yes — write a plugin and
drop it in `plugins/`. See the
[plugin development guide](https://fastcms.org/docs/plugins/plugin-development).

**Is it production-ready?** The current release is `0.1.x` — APIs may
still evolve before `1.0`. Several teams run it in production today; see
[CHANGELOG.md](CHANGELOG.md) for what's stable and what's recently
fixed.

**Hit an error?** Check the
[Troubleshooting guide](https://fastcms.org/docs/troubleshooting) — it
covers the common install, boot, plugin, and deployment failures with
the exact fix for each.

---

## License

MIT — see [LICENSE](LICENSE).
