# Changelog

All notable changes to **pyfastcms** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
