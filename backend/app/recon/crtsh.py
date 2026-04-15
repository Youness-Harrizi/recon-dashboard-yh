"""Certificate Transparency subdomain enumeration via crt.sh.

Passive — crt.sh aggregates public CT logs. No packets are sent to the target.
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.recon.base import Context, FindingDraft

MAX_SUBDOMAINS = 500


class CrtShModule:
    name = "crtsh"
    passive = True

    def run(self, ctx: Context) -> None:
        url = "https://crt.sh/"
        try:
            r = httpx.get(
                url,
                params={"q": f"%.{ctx.domain}", "output": "json"},
                timeout=30,
                headers={"User-Agent": settings.user_agent},
            )
            r.raise_for_status()
            rows = r.json()
        except Exception as exc:
            ctx.emit(
                FindingDraft(
                    module=self.name,
                    title="crt.sh lookup failed",
                    data={"error": f"{type(exc).__name__}: {exc}"},
                )
            )
            return

        found: set[str] = set()
        for row in rows:
            raw = (row.get("name_value") or "").strip().lower()
            for entry in raw.split("\n"):
                entry = entry.strip().lstrip("*.")
                if entry and (entry == ctx.domain or entry.endswith("." + ctx.domain)):
                    found.add(entry)

        found.discard(ctx.domain)
        subs = sorted(found)
        truncated = len(subs) > MAX_SUBDOMAINS
        ctx.emit(
            FindingDraft(
                module=self.name,
                title=f"{len(subs)} subdomain(s) from certificate transparency",
                data={
                    "total": len(subs),
                    "truncated": truncated,
                    "subdomains": subs[:MAX_SUBDOMAINS],
                },
            )
        )
