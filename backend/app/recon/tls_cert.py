"""TLS handshake + certificate inspection.

Technically active (opens a TCP+TLS connection to :443), but indistinguishable
from a normal browser visit and carries no scanning payload.
"""

from __future__ import annotations

import socket
import ssl
from datetime import datetime, timezone
from typing import Any

from app.models.finding import Severity
from app.recon.base import Context, FindingDraft


def _flatten_rdn(rdn_seq: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if not rdn_seq:
        return out
    for rdn in rdn_seq:
        for k, v in rdn:
            out[k] = v
    return out


class TlsModule:
    name = "tls"
    passive = False

    def run(self, ctx: Context) -> None:
        ssl_ctx = ssl.create_default_context()
        try:
            with socket.create_connection((ctx.domain, 443), timeout=10) as sock:
                with ssl_ctx.wrap_socket(sock, server_hostname=ctx.domain) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
        except Exception as exc:
            ctx.emit(
                FindingDraft(
                    module=self.name,
                    title="TLS handshake failed",
                    data={"error": f"{type(exc).__name__}: {exc}"},
                )
            )
            return

        issuer = _flatten_rdn(cert.get("issuer"))
        subject = _flatten_rdn(cert.get("subject"))
        san = [v for k, v in (cert.get("subjectAltName") or []) if k == "DNS"]

        not_before = cert.get("notBefore")
        not_after = cert.get("notAfter")
        days_left: int | None = None
        severity = Severity.info
        title = f"TLS {version} certificate from {issuer.get('organizationName') or issuer.get('commonName') or '?'}"

        if not_after:
            try:
                expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(
                    tzinfo=timezone.utc
                )
                days_left = (expiry - datetime.now(timezone.utc)).days
                if days_left < 0:
                    severity = Severity.high
                    title = f"TLS certificate EXPIRED {-days_left} days ago"
                elif days_left < 14:
                    severity = Severity.medium
                    title = f"TLS certificate expires in {days_left} days"
                else:
                    title = f"TLS {version} — cert valid {days_left} more days"
            except ValueError:
                pass

        ctx.emit(
            FindingDraft(
                module=self.name,
                title=title,
                severity=severity,
                data={
                    "tls_version": version,
                    "cipher": cipher[0] if cipher else None,
                    "issuer": issuer,
                    "subject": subject,
                    "not_before": not_before,
                    "not_after": not_after,
                    "days_until_expiry": days_left,
                    "san": san[:50],
                    "san_total": len(san),
                },
            )
        )
