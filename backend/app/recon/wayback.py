"""Historical URL discovery via the Wayback Machine's CDX API."""

from __future__ import annotations

import httpx

from app.config import settings
from app.recon.base import Context, FindingDraft

MAX_URLS = 300


class WaybackModule:
    name = "wayback"
    passive = True

    def run(self, ctx: Context) -> None:
        url = "https://web.archive.org/cdx/search/cdx"
        params = {
            "url": f"{ctx.domain}/*",
            "output": "json",
            "fl": "timestamp,original,statuscode,mimetype",
            "collapse": "urlkey",
            "limit": str(MAX_URLS),
        }
        try:
            r = httpx.get(
                url,
                params=params,
                timeout=30,
                headers={"User-Agent": settings.user_agent},
            )
            r.raise_for_status()
            rows = r.json()
        except Exception as exc:
            ctx.emit(
                FindingDraft(
                    module=self.name,
                    title="Wayback Machine lookup failed",
                    data={"error": f"{type(exc).__name__}: {exc}"},
                )
            )
            return

        if not isinstance(rows, list) or len(rows) < 2:
            ctx.emit(
                FindingDraft(
                    module=self.name,
                    title=f"No archived snapshots for {ctx.domain}",
                )
            )
            return

        # The first row is the header.
        records = [
            {
                "timestamp": row[0],
                "url": row[1],
                "status": row[2],
                "mime": row[3] if len(row) > 3 else None,
            }
            for row in rows[1:]
        ]

        ctx.emit(
            FindingDraft(
                module=self.name,
                title=f"{len(records)} archived URLs in Wayback Machine",
                data={
                    "total": len(records),
                    "truncated": len(records) >= MAX_URLS,
                    "urls": records,
                },
            )
        )
