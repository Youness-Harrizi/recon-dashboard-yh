# Recon

Self-hosted domain reconnaissance dashboard. Given a domain, runs passive recon modules (DNS, WHOIS, certificate transparency, tech fingerprinting, Wayback, etc.) and streams findings to a web UI.

**Status:** step 5 — seven real passive-ish recon modules wired up (`dns`, `whois`, `crtsh`, `tls`, `http`, `wayback`, `github`). Enter a domain and watch findings stream in live.

## Stack

- **Backend:** FastAPI (async), SQLAlchemy 2, asyncpg
- **Workers:** Celery + Redis (added in step 3)
- **DB:** PostgreSQL 16
- **Cache/queue:** Redis 7
- **Frontend:** Next.js 15 (App Router) + TypeScript
- **Packaging:** Docker Compose

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- Web UI: http://localhost:3000
- API:    http://localhost:8000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

The landing page pings `/health` and shows DB + Redis status. If both are `ok`, the scaffolding is working.

## Layout

```
backend/   FastAPI app (app/main.py, app/config.py) + Dockerfile
web/       Next.js app (src/app/page.tsx) + Dockerfile
docker-compose.yml
```

## API

```
POST /api/v1/scans              { "domain": "example.com" } → Scan
GET  /api/v1/scans              → Scan[] (most recent first)
GET  /api/v1/scans/{id}         → ScanDetail (includes findings + module_runs)
GET  /api/v1/scans/{id}/stream  → SSE: snapshot, module_run, finding, scan, end
GET  /health                    → dependency status
```

Domain input is normalized (strips `https://`, paths, trailing dot, IDN→punycode) and rejected if it's an IP, `localhost`, or a reserved TLD like `.local`/`.internal`.

## Migrations

Migrations run automatically on backend container startup (`alembic upgrade head`). To create a new revision while developing:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe change"
docker compose exec backend alembic upgrade head
```

## Architecture

```
POST /api/v1/scans
   ↓ persists Scan(status=pending) + ModuleRun rows
   ↓ dispatches Celery chord
           ┌──────────────────────────┐
           │ run_module(scan, name)   │  × N modules in parallel
           │   → emit() → Finding rows│
           │   → update ModuleRun     │
           └─────────────┬────────────┘
                         ↓ chord callback
           finalize_scan → Scan.status = done|failed
```

Modules implement a tiny Protocol (`app/recon/base.py`) and register themselves in `app/recon/registry.py`.

## Modules

| Module    | What it does                                                         | Source                                   |
|-----------|----------------------------------------------------------------------|------------------------------------------|
| `dns`     | Resolves A/AAAA/MX/NS/TXT/CNAME/SOA, flags missing SPF / DMARC       | Public resolvers via `dnspython`         |
| `whois`   | RDAP: registrar, registration/expiration dates, nameservers, status  | `rdap.org` (follows to authoritative)    |
| `crtsh`   | Subdomain enumeration from Certificate Transparency logs             | `crt.sh?output=json`                     |
| `tls`     | Handshakes :443, parses cert (issuer, SAN, expiry + severity tiers)  | `ssl.create_default_context()`           |
| `http`    | GETs `/`, inspects headers, missing security headers, tech markers   | Direct HTTPS                             |
| `wayback` | Historical URLs for the domain                                       | `web.archive.org/cdx/search/cdx`         |
| `github`  | Public code mentioning the domain (leaked configs, hardcoded URLs)   | GitHub code search API (needs token)     |

Set `GITHUB_TOKEN` in `.env` to enable the `github` module — it skips gracefully otherwise.

## Live updates

Each worker publishes state changes (module status, new findings, scan done) on a Redis pub/sub channel (`scan:<id>`). The API exposes `GET /api/v1/scans/{id}/stream` as a Server-Sent Events endpoint that replays a snapshot then forwards every subsequent event to the browser — no polling, updates appear the instant they're persisted. The UI falls back to polling if the SSE connection fails.

## Next steps

6. Polish: caching via `domain_cache`, JSON/PDF export, slowapi rate limiting, tests.
