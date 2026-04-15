# Recon

Self-hosted domain reconnaissance dashboard. Given a domain, runs passive recon modules (DNS, WHOIS, certificate transparency, tech fingerprinting, Wayback, etc.) and streams findings to a web UI.

**Status:** step 2 — data model + scan API. Scans persist to Postgres; orchestrator lands in step 3.

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
POST /api/v1/scans           { "domain": "example.com" } → Scan
GET  /api/v1/scans           → Scan[] (most recent first)
GET  /api/v1/scans/{id}      → ScanDetail (includes findings + module_runs)
GET  /health                 → dependency status
```

Domain input is normalized (strips `https://`, paths, trailing dot, IDN→punycode) and rejected if it's an IP, `localhost`, or a reserved TLD like `.local`/`.internal`.

## Migrations

Migrations run automatically on backend container startup (`alembic upgrade head`). To create a new revision while developing:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe change"
docker compose exec backend alembic upgrade head
```

## Next steps

3. Orchestrator + Celery + one dummy module that emits fake findings.
4. SSE streaming endpoint and live-updating UI (replace the current 2s poll).
5. Real recon modules: dns → whois → crtsh → tls → http → wayback → github.
