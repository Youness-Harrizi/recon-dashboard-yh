"""HTTP fingerprint: fetch the root page, inspect headers & security posture."""

from __future__ import annotations

import re

import httpx

from app.config import settings
from app.models.finding import Severity
from app.recon.base import Context, FindingDraft

SECURITY_HEADERS = [
    "content-security-policy",
    "strict-transport-security",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
    "permissions-policy",
]

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
GENERATOR_RE = re.compile(
    r'<meta\s+name=["\']generator["\']\s+content=["\']([^"\']+)', re.IGNORECASE
)


class HttpModule:
    name = "http"
    passive = False

    def run(self, ctx: Context) -> None:
        url = f"https://{ctx.domain}/"
        try:
            r = httpx.get(
                url,
                timeout=15,
                follow_redirects=True,
                headers={"User-Agent": settings.user_agent},
            )
        except Exception as exc:
            ctx.emit(
                FindingDraft(
                    module=self.name,
                    title=f"HTTPS request failed: {type(exc).__name__}",
                    data={"error": str(exc), "url": url},
                )
            )
            return

        headers_lower = {k.lower(): v for k, v in r.headers.items()}
        body = r.text[:200_000]  # cap body in case of giant pages
        title_match = TITLE_RE.search(body)
        generator_match = GENERATOR_RE.search(body)

        missing = [h for h in SECURITY_HEADERS if h not in headers_lower]
        severity = Severity.info
        if len(missing) >= 4:
            severity = Severity.low
        if len(missing) >= 6:
            severity = Severity.medium

        ctx.emit(
            FindingDraft(
                module=self.name,
                title=f"HTTP {r.status_code} — {headers_lower.get('server', 'unknown server')}",
                severity=severity,
                data={
                    "final_url": str(r.url),
                    "status": r.status_code,
                    "redirect_chain": [str(h.url) for h in r.history],
                    "server": headers_lower.get("server"),
                    "powered_by": headers_lower.get("x-powered-by"),
                    "content_type": headers_lower.get("content-type"),
                    "title": (title_match.group(1).strip()[:200] if title_match else None),
                    "generator": generator_match.group(1) if generator_match else None,
                    "cookies": [c.name for c in r.cookies.jar],
                    "missing_security_headers": missing,
                    "present_security_headers": [
                        h for h in SECURITY_HEADERS if h in headers_lower
                    ],
                },
            )
        )
