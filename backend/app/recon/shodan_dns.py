"""Shodan passive DNS + service fingerprinting.

Uses two endpoints:
  /dns/domain/{domain}  — subdomains + DNS records Shodan has observed
  /shodan/host/search   — hostname:<domain> → open ports / services / banners

Both are queried passively (no packets to target). Requires a Shodan API key;
the module skips gracefully if SHODAN_API_KEY is unset.
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.models.finding import Severity
from app.recon.base import Context, FindingDraft

BASE = "https://api.shodan.io"
TIMEOUT = 30

# Ports that raise eyebrows when publicly reachable — used for severity bump.
RISKY_PORTS = {21, 23, 3306, 3389, 5432, 5900, 6379, 9200, 11211, 27017, 27018}


class ShodanModule:
    name = "shodan"
    passive = True

    def run(self, ctx: Context) -> None:
        key = settings.shodan_api_key
        if not key:
            ctx.emit(
                FindingDraft(
                    module=self.name,
                    title="Skipped: SHODAN_API_KEY not set",
                    data={
                        "hint": "Set SHODAN_API_KEY in .env. Free tier is enough for /dns/domain."
                    },
                )
            )
            return

        self._passive_dns(ctx, key)
        self._host_search(ctx, key)

    # ---- /dns/domain --------------------------------------------------------

    def _passive_dns(self, ctx: Context, key: str) -> None:
        try:
            r = httpx.get(
                f"{BASE}/dns/domain/{ctx.domain}",
                params={"key": key},
                timeout=TIMEOUT,
                headers={"User-Agent": settings.user_agent},
            )
            if r.status_code == 401:
                ctx.emit(
                    FindingDraft(
                        module=self.name,
                        title="Shodan: API key rejected (401)",
                        severity=Severity.medium,
                        data={"hint": "Check SHODAN_API_KEY; rotate if exposed."},
                    )
                )
                return
            if r.status_code == 404:
                ctx.emit(
                    FindingDraft(
                        module=self.name,
                        title="Shodan has no DNS data for this domain",
                    )
                )
                return
            r.raise_for_status()
            body = r.json()
        except Exception as exc:
            ctx.emit(
                FindingDraft(
                    module=self.name,
                    title="Shodan /dns/domain lookup failed",
                    data={"error": f"{type(exc).__name__}: {exc}"},
                )
            )
            return

        subdomains = sorted(set(body.get("subdomains") or []))
        records = body.get("data") or []
        tags = body.get("tags") or []

        ctx.emit(
            FindingDraft(
                module=self.name,
                title=f"Shodan passive DNS: {len(subdomains)} subdomain(s), {len(records)} record(s)",
                data={
                    "subdomains": subdomains[:500],
                    "subdomain_total": len(subdomains),
                    "subdomain_truncated": len(subdomains) > 500,
                    "records": records[:500],
                    "tags": tags,
                },
            )
        )

    # ---- /shodan/host/search (hostname:<domain>) ----------------------------

    def _host_search(self, ctx: Context, key: str) -> None:
        try:
            r = httpx.get(
                f"{BASE}/shodan/host/search",
                params={"key": key, "query": f"hostname:{ctx.domain}", "minify": "true"},
                timeout=TIMEOUT,
                headers={"User-Agent": settings.user_agent},
            )
            if r.status_code == 401:
                return  # already reported above
            if r.status_code == 403:
                # Paid-tier endpoint. Free keys can still use /dns/domain, so
                # this is expected — report once, no severity bump.
                ctx.emit(
                    FindingDraft(
                        module=self.name,
                        title="Shodan host search unavailable on this API tier (403)",
                        data={"hint": "Free keys only get /dns/domain; host search needs a paid plan."},
                    )
                )
                return
            r.raise_for_status()
            body = r.json()
        except Exception as exc:
            ctx.emit(
                FindingDraft(
                    module=self.name,
                    title="Shodan host search failed",
                    data={"error": f"{type(exc).__name__}: {exc}"},
                )
            )
            return

        matches = body.get("matches") or []
        total = body.get("total", 0)

        # Collapse to one row per (ip, port) with banner/product info.
        services: list[dict] = []
        open_risky_ports: set[int] = set()
        for m in matches[:200]:
            port = m.get("port")
            services.append(
                {
                    "ip": m.get("ip_str"),
                    "port": port,
                    "transport": m.get("transport"),
                    "product": m.get("product"),
                    "version": m.get("version"),
                    "hostnames": m.get("hostnames", []),
                    "org": m.get("org"),
                    "location": (m.get("location") or {}).get("country_code"),
                }
            )
            if isinstance(port, int) and port in RISKY_PORTS:
                open_risky_ports.add(port)

        severity = Severity.info
        if open_risky_ports:
            severity = Severity.medium

        ctx.emit(
            FindingDraft(
                module=self.name,
                title=f"Shodan host search: {total} service(s) for hostname:{ctx.domain}",
                severity=severity,
                data={
                    "total": total,
                    "services": services,
                    "risky_ports_exposed": sorted(open_risky_ports),
                },
            )
        )
