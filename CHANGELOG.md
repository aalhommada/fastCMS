# Changelog

All notable changes to **pyfastcms** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.6] — 2026-05-11

UX improvements and admin-page-routing fix.

### Added

- **`fastcms dev` auto-opens the browser** at `http://127.0.0.1:<port>/admin`
  once `/health` responds. A health-poll loop runs in a background
  thread so the browser opens at the right moment (not too early during
  cold boot). Opt out with `--no-open`.
- Package description updated to "AI-native Backend-as-a-Service built
  with FastAPI" to reflect the product identity.

### Fixed

- **`/admin/plugins` page**: each plugin row's button used to be a
  "Settings" link pointing to a JSON API endpoint, which rendered as
  `{}` in the browser. Now shows an **Open** button only when the
  plugin has a registered admin UI (e.g. AI Core → `/admin/ai`), and
  displays a muted "No admin page" label otherwise. Backed by a new
  `admin_pages` map passed to the template (plugin_id → URL).

### Changed

- Reframed copy across README and docs to lead with AI identity:
  "AI-native Python BaaS — RAG, vector search, autonomous agents".
  The lightweight-core / opt-in-plugins angle is preserved but now
  framed as *how* AI is delivered, not a substitute for the AI
  narrative.

## [0.1.5] — 2026-05-11

Critical fix for users installing on Python 3.13+ / Starlette 1.0+.

### Fixed

- **`/admin/*` routes 500'd on fresh installs** with the error
  `TypeError: cannot use 'tuple' as a dict key (unhashable type: 'dict')`
  on any Starlette ≥ ~0.40 / Python 3.14. All 29 calls in
  `app/admin/routes.py` were using the deprecated
  `TemplateResponse(name, {"request": request, ...})` signature. On
  newer Starlette, the first positional arg is now the `Request`
  instance — the old form was being misinterpreted (`name="login.html"`
  treated as the request, the context dict treated as the template
  name) and Jinja2 crashed trying to use a dict as a cache key.
- Migrated all admin templates to the modern API:
  `TemplateResponse(request, name, context)`. Backward-compatible with
  Starlette ≥ 0.31 (both APIs supported there).

### Migration notes

If you only used `0.1.3` or `0.1.4`: just upgrade to `0.1.5`. No
configuration or schema changes needed.

If you had a `pip install pyfastcms` from a fresh environment that 500'd
on `/admin`, this is the fix.

## [0.1.4] — 2026-05-11

Tooling + documentation patch: standardise on `uv` as the Python toolchain
and add a complete Docker deployment guide. No runtime behaviour changes.

### Added

- `.python-version` pinning the toolchain to Python 3.13 so `uv` and
  `pyenv` both auto-pick the right interpreter.
- `[tool.uv]` block in `pyproject.toml` declaring the dev environment.
  `uv sync --all-extras` now creates a complete development setup in
  one command.
- Deployment guide at <https://fastcms.org/docs/deployment/docker>
  (Docker + Postgres + Redis quickstart, env config, persistence,
  reverse proxy, scaling notes, backups).

### Changed

- **Dockerfile rewritten to use `uv`** for dependency installation.
  Multi-stage build now resolves and installs with `uv pip install`
  instead of `pip install`. Cold builds are ~3× faster (≈30 s vs ≈90 s)
  and warm builds ≈3 s. Same final image, deterministic.
- **README install section rewritten** with `uv` as the recommended
  path: `uv tool install pyfastcms` (treats `fastcms` like a system
  CLI tool) is now the first install option. `pip` is preserved as a
  documented fallback.
- `fastcms init` project scaffold updated to reference `uv add` for
  extra dependencies and point at `fastcms.org` for docs.
- Docs site (`fastcms.org`) install snippets across getting-started,
  CLI reference, plugin pages, and landing-page hero migrated to
  `uv pip install` / `uv tool install`.

### Migration notes

- Existing `pip install pyfastcms` users: nothing breaks — pip still
  works. Switching to `uv tool install pyfastcms` is recommended but
  optional.
- Existing Docker users: rebuild (`docker compose build`) once to pick
  up the faster image. No compose-file changes required.

## [0.1.3] — 2026-05-08

Documentation-only patch fixing docs URLs in the package README.

### Fixed

- README now points to the correct docs site (`fastcms.org`) instead of
  `fastcms.dev`. Affects 10 doc links plus the "Full docs" reference.
  All other content unchanged from 0.1.2.

## [0.1.2] — 2026-05-08

Documentation-only patch release. No code changes.

### Changed

- **README rewritten** to lead with `pip install pyfastcms` and the
  `fastcms` CLI (the previous README walked users through `git clone` and
  manual venv setup, which is the wrong audience for the pypi page).
- New tagline: *"The modular Python BaaS — auth, realtime, files, dynamic
  collections. AI via plugins, install only what you need."*
- Quick-start curl examples now use the correct `{"data": {...}}` envelope
  (the previous examples sent fields at the top level, which doesn't match
  the actual API contract).
- AI section consolidated to a single block with the working
  `fastcms plugin install ai-core` command, replacing two scattered "AI
  Features (via Plugins)" mentions.
- Added install paths for cloud-storage extras (`pyfastcms[s3]`,
  `pyfastcms[azure]`, `pyfastcms[storage]`) and Docker.

## [0.1.1] — 2026-05-08

A patch release that fixes critical bugs in the event spine (webhooks +
realtime) and dynamic-collections query layer. No API surface changes — drop
in over 0.1.0.

### Fixed

- **Webhooks were never delivered.** `_trigger_webhooks` imported a name that
  didn't exist (`async_session_maker` instead of `AsyncSessionLocal`); every
  record event silently logged "Webhook delivery failed" and never fired the
  HTTP POST.
- **Webhook event-type matching was broken.** Internal `EventType.RECORD_CREATED.value`
  is `"record.created"` but the public webhook contract uses
  `["create","update","delete"]`. The mismatch meant no webhook ever matched
  any event.
- **Webhook HMAC signatures were unverifiable.** The signature was computed
  over `json.dumps(payload)` but the request was sent via `httpx.post(json=...)`
  which uses different separators — receivers always got `MISMATCH`.
- **4xx webhook responses were logged as `success: true`.** Now correctly
  treated as permanent failures (no retry, `success: false` in delivery log).
- **Realtime events were delivered twice.** Every event published to both
  `collection:X` and `global:events` channels and the listener delivered to
  every matching connection on both. Listener now dispatches by channel type.
- **`@today` / `@todayStart` / `@monthStart` filters returned 0 rows for
  same-day comparisons.** SQLite stores DATETIME with a space separator
  (`2026-05-06 11:03`) but `datetime.isoformat()` uses `T` — string
  comparison failed when the date matched today. Macros now return `datetime`
  objects so SQLAlchemy binds them correctly.
- **Modifying a collection schema (drop field) caused 500 + raw SQL leak**
  on the next record write. Stale `Table` in SQLAlchemy `MetaData` was reused
  with `extend_existing=True`, keeping the dropped column. `clear_cache` now
  also drops the cached `Table`.
- **`skipTotal=true` returned `total: -1` and `total_pages: -1` instead of
  `null`.** `RecordListResponse.total` and `total_pages` are now
  `Optional[int]` and the service returns `None` when skipped.

### Added

- `GET /api/v1/hooks` — admin-only endpoint listing loaded hook files
  (`{file, module, functions}`). The endpoint was documented but never
  implemented in 0.1.0.

### Changed

- `_generate_signature` accepts both `str` and `bytes` payloads (bytes is
  preferred — sign exactly what gets sent).

## [0.1.0] — 2026-03-16

Initial pip-installable release.
