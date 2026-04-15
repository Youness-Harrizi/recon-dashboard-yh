"""Search public GitHub code for references to the target domain.

Useful for catching leaked configs, hardcoded URLs, committed secrets that
reference the domain, etc. Requires GITHUB_TOKEN — otherwise the module emits
a skip finding so the user knows why they got no results.
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.models.finding import Severity
from app.recon.base import Context, FindingDraft


class GithubDorksModule:
    name = "github"
    passive = True

    def run(self, ctx: Context) -> None:
        token = settings.github_token
        if not token:
            ctx.emit(
                FindingDraft(
                    module=self.name,
                    title="Skipped: GITHUB_TOKEN not set",
                    data={
                        "hint": "Set GITHUB_TOKEN in .env to enable public-code search for references to this domain"
                    },
                )
            )
            return

        try:
            r = httpx.get(
                "https://api.github.com/search/code",
                params={"q": f'"{ctx.domain}"', "per_page": 30},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": settings.user_agent,
                },
                timeout=30,
            )
            if r.status_code == 403:
                ctx.emit(
                    FindingDraft(
                        module=self.name,
                        title="GitHub search rate-limited or token lacks scope",
                        data={"status": 403, "body": r.text[:500]},
                    )
                )
                return
            r.raise_for_status()
            body = r.json()
        except Exception as exc:
            ctx.emit(
                FindingDraft(
                    module=self.name,
                    title="GitHub search failed",
                    data={"error": f"{type(exc).__name__}: {exc}"},
                )
            )
            return

        items = body.get("items", []) or []
        total = body.get("total_count", 0)
        sample = [
            {
                "repo": (it.get("repository") or {}).get("full_name"),
                "path": it.get("path"),
                "url": it.get("html_url"),
            }
            for it in items
        ]

        severity = Severity.low if total > 0 else Severity.info
        ctx.emit(
            FindingDraft(
                module=self.name,
                title=f"{total} GitHub code reference(s) to {ctx.domain}",
                severity=severity,
                data={"total": total, "sample": sample},
            )
        )
