"""Smoke test for the DNS module with dnspython mocked out.

Keeps the suite hermetic — no real DNS traffic in CI.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import dns.resolver

from app.models.finding import Severity
from app.recon.base import Context, FindingDraft
from app.recon.dns_records import DnsModule


def _collect() -> tuple[list[FindingDraft], Context]:
    findings: list[FindingDraft] = []
    ctx = Context(
        domain="example.com",
        scan_id=uuid.uuid4(),
        emit=lambda d: findings.append(d),
    )
    return findings, ctx


def _answer(values: list[str]) -> list[MagicMock]:
    return [MagicMock(**{"to_text.return_value": v}) for v in values]


def test_flags_missing_spf_and_dmarc() -> None:
    findings, ctx = _collect()

    def fake_resolve(name: str, rtype: str):
        # Return a bare A record, nothing else.
        if rtype == "A":
            return _answer(["93.184.216.34"])
        raise dns.resolver.NoAnswer()

    with patch.object(dns.resolver.Resolver, "resolve", side_effect=fake_resolve):
        DnsModule().run(ctx)

    titles = [f.title for f in findings]
    assert any("A records" in t for t in titles)
    assert any("No SPF record" in t for t in titles)
    assert any("No DMARC" in t for t in titles)

    severities = {f.title: f.severity for f in findings}
    assert severities["No SPF record (v=spf1) found"] == Severity.low


def test_records_spf_presence() -> None:
    findings, ctx = _collect()

    def fake_resolve(name: str, rtype: str):
        if name == "example.com" and rtype == "TXT":
            return _answer(['"v=spf1 -all"'])
        if name == "_dmarc.example.com" and rtype == "TXT":
            return _answer(['"v=DMARC1; p=reject"'])
        raise dns.resolver.NoAnswer()

    with patch.object(dns.resolver.Resolver, "resolve", side_effect=fake_resolve):
        DnsModule().run(ctx)

    titles = [f.title for f in findings]
    assert not any("No SPF" in t for t in titles)
    assert any("DMARC policy found" in t for t in titles)
