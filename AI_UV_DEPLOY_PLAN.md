# Plan — Migrate FastCMS to uv + add Docker deployment docs

**Trigger:** the README/quickstart docs assume `pip` is on PATH. First-time
users on macOS hit `zsh: command not found: pip`. Move everything to `uv` —
the modern Python toolchain — and document Docker as the production path.

**Out of scope:** removing the plugin-based AI architecture (still
opt-in); deleting the existing pip-as-fallback paths from the README.

---

## Scope by repo

### fastCMS package
- `pyproject.toml` — add `[tool.uv]` block; declare `[project.optional-dependencies] dev`; clarify python pin
- `.python-version` (new) — pin to 3.13 (matches Dockerfile) so `uv` auto-installs the right interpreter
- `Dockerfile` — multi-stage build using `uv` instead of pip; faster builds, smaller image, single command for sync
- `README.md` — install section rewritten to lead with `uv` (with pipx + pip as fallbacks); add Docker quickstart
- `cli/commands/init.py` — generated project scaffolds should reference `uv` not `pip` in their `.env` / README templates
- `docker-compose.yml` — verify SECRET_KEY env handling is documented; reference new docs
- `CHANGELOG.md` — 0.1.4 entry
- Version bump: 0.1.3 → 0.1.4 in 5 files

### fastcms-docs
- `content/docs/getting-started/index.mdx` — `pip install`/`python -m venv` → uv equivalents
- `content/docs/getting-started/cli.mdx` — installation and troubleshooting tips → uv-first
- `content/docs/plugins/ai-rag.mdx` — optional `pip install PyPDF2` → `uv pip install PyPDF2`
- `content/docs/plugins/ai-vectors.mdx` — `pip install numpy` → `uv pip install numpy`
- `content/docs/plugins/langflow.mdx` — `pip install langflow` → `uv pip install langflow`
- `content/docs/sdk/python.mdx` — `pip install fastcms-py` → `uv pip install fastcms-py`
- `components/landing/hero.tsx` — terminal animation: `pip install pyfastcms` → `uv pip install pyfastcms`
- `components/landing/footer.tsx` — `pip install` mention → `uv pip install`
- `components/landing/how-it-works.tsx` — `pip install` step → `uv pip install`
- New: `content/docs/deployment/` directory with:
  - `meta.json` (nav config)
  - `docker.mdx` (the actual deployment walkthrough)

### fastcms-plugins
- No code changes (plugins don't have their own pip dep). Maybe a one-line
  note in the README that the plugins live alongside the parent install.

---

## uv usage patterns we'll standardise on

**End user installing the published package:**
```
uv tool install pyfastcms       # installs as an isolated CLI tool — RECOMMENDED for `fastcms` CLI
                                # OR
uv pip install pyfastcms        # installs into the active env — for app/library usage
```

**End user creating a project:**
```
uv init my-app && cd my-app
uv add pyfastcms
uv run fastcms dev
```

**Contributor / source install:**
```
git clone <repo> && cd fastCMS
uv venv && source .venv/bin/activate
uv pip install -e '.[dev,storage]'
```

**Docker (production):**
```
docker compose up -d
```

---

## Dockerfile redesign — key changes

Current Dockerfile uses pip in a two-stage build (builder → runtime). New
Dockerfile uses `uv` end-to-end:

1. **Builder stage:** install `uv`, then `uv pip install` into `/opt/venv`
2. **Runtime stage:** copy `/opt/venv`, install only runtime libs
3. **Add `uv pip install --no-cache` to keep image small**
4. **Pin Python via `.python-version` so the build is reproducible**

Net effect: build goes from ~2 min to ~30 s on cold cache, ~10 s on warm.

---

## New deployment docs page

`content/docs/deployment/docker.mdx` will cover:

1. **Quickstart (single host)** — `docker compose up -d` with the included
   compose file, Postgres + Redis + FastCMS, SECRET_KEY via .env
2. **Configuration** — env vars that matter for production
3. **Persistence** — volume mounts for data/files, db, plugins
4. **Reverse proxy** — Caddy / nginx examples for TLS
5. **Scaling** — Redis pub/sub for multi-instance, sticky sessions, what
   to expect at >10 instances
6. **Backups** — using FastCMS's built-in backup API + scheduling
7. **Health checks + observability** — `/health` endpoint, log shipping
8. **Common pitfalls** — SECRET_KEY rotation, CORS, file storage to S3
   when scaling beyond one host

---

## Execution order

1. Save this plan ✓
2. fastCMS package changes (Dockerfile + pyproject + .python-version + cli/init + README + CHANGELOG + version)
3. fastcms-docs MDX changes (8 files)
4. New deployment/docker.mdx page + meta.json
5. Verify: clean venv smoke test (`uv pip install dist/pyfastcms-0.1.4-*.whl`, `fastcms --version`, `fastcms init` template inspection)
6. Build wheels, twine check
7. Generate the commit commands (you push)

I won't push or publish anything; you do all `git push` and `twine upload`
yourself as before. Final output will be a clean diff + the upload commands.
