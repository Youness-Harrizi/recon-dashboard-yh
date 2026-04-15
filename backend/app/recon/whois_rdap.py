"""WHOIS-equivalent via RDAP. JSON-structured, no rate limit headaches."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.recon.base import Context, FindingDraft


def _registrar_name(body: dict[str, Any]) -> str | None:
    for ent in body.get("entities", []) or []:
        if "registrar" in (ent.get("roles") or []):
            vcard = ent.get("vcardArray")
            if isinstance(vcard, list) and len(vcard) >= 2:
                for item in vcard[1]:
                    if isinstance(item, list) and len(item) >= 4 and item[0] == "fn":
                        return item[3]
    return None


def _event(body: dict[str, Any], action: str) -> str | None:
    for ev in body.get("events", []) or []:
        if ev.get("eventAction") == action:
            return ev.get("eventDate")
    return None


class WhoisModule:
    name = "whois"
    passive = True

    def run(self, ctx: Context) -> None:
        url = f"https://rdap.org/domain/{ctx.domain}"
        try:
            r = httpx.get(
                url,
                follow_redirects=True,
                timeout=15,
                headers={"User-Agent": settings.user_agent, "Accept": "application/rdap+json"},
            )
            if r.status_code == 404:
                ctx.emit(
                    FindingDraft(
                        module=self.name,
                        title="RDAP: domain not found",
                        data={"status": 404},
                    )
                )
                return
            r.raise_for_status()
            body = r.json()
        except Exception as exc:
            ctx.emit(
                FindingDraft(
                    module=self.name,
                    title="RDAP lookup failed",
                    data={"error": f"{type(exc).__name__}: {exc}"},
                )
            )
            return

        nameservers = sorted(
            {ns.get("ldhName", "").lower() for ns in body.get("nameservers", []) or [] if ns.get("ldhName")}
        )

        ctx.emit(
            FindingDraft(
                module=self.name,
                title=f"Registration info for {ctx.domain}",
                data={
                    "registrar": _registrar_name(body),
                    "registered": _event(body, "registration"),
                    "expires": _event(body, "expiration"),
                    "last_changed": _event(body, "last changed"),
                    "status": body.get("status", []),
                    "nameservers": nameservers,
                    "ldh_name": body.get("ldhName"),
                },
            )
        )
