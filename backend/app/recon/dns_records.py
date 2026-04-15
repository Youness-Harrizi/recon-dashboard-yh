"""DNS recon: resolve the common record types and flag missing DMARC."""

from __future__ import annotations

import dns.exception
import dns.resolver

from app.models.finding import Severity
from app.recon.base import Context, FindingDraft

RECORD_TYPES = ("A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA")


def _resolver() -> dns.resolver.Resolver:
    r = dns.resolver.Resolver()
    r.lifetime = 5.0
    r.timeout = 5.0
    return r


class DnsModule:
    name = "dns"
    passive = True

    def run(self, ctx: Context) -> None:
        resolver = _resolver()
        txt_records: list[str] = []

        for rtype in RECORD_TYPES:
            try:
                answers = resolver.resolve(ctx.domain, rtype)
            except (
                dns.resolver.NoAnswer,
                dns.resolver.NXDOMAIN,
                dns.resolver.NoNameservers,
                dns.exception.Timeout,
            ):
                continue
            except Exception as exc:
                ctx.emit(
                    FindingDraft(
                        module=self.name,
                        title=f"{rtype} lookup error",
                        data={"error": f"{type(exc).__name__}: {exc}"},
                    )
                )
                continue

            values = sorted({a.to_text() for a in answers})
            if rtype == "TXT":
                txt_records = values
            ctx.emit(
                FindingDraft(
                    module=self.name,
                    title=f"{rtype} records ({len(values)})",
                    data={"type": rtype, "values": values},
                )
            )

        # SPF presence check (from TXT records we already fetched).
        has_spf = any("v=spf1" in t.lower() for t in txt_records)
        if not has_spf:
            ctx.emit(
                FindingDraft(
                    module=self.name,
                    title="No SPF record (v=spf1) found",
                    severity=Severity.low,
                    data={"recommendation": "Publish an SPF record to prevent spoofing"},
                )
            )

        # DMARC lookup on the _dmarc subdomain.
        try:
            dmarc = resolver.resolve(f"_dmarc.{ctx.domain}", "TXT")
            dmarc_vals = sorted({r.to_text() for r in dmarc})
            ctx.emit(
                FindingDraft(
                    module=self.name,
                    title="DMARC policy found",
                    data={"values": dmarc_vals},
                )
            )
        except (
            dns.resolver.NoAnswer,
            dns.resolver.NXDOMAIN,
            dns.resolver.NoNameservers,
            dns.exception.Timeout,
        ):
            ctx.emit(
                FindingDraft(
                    module=self.name,
                    title="No DMARC policy at _dmarc.{domain}".format(domain=ctx.domain),
                    severity=Severity.low,
                    data={
                        "recommendation": "Publish _dmarc TXT record with at least p=none to enable monitoring"
                    },
                )
            )
