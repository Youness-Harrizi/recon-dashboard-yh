"""Central registry of enabled recon modules.

Adding a module = import it here and put it in MODULES. The orchestrator reads
this list to fan out work; unit tests use it to assert coverage.

Order in MODULES is cosmetic only — Celery dispatches them in parallel. It's
kept roughly in order of cheapest → slowest so the UI fills in fast at the top.
"""

from __future__ import annotations

from app.recon.base import ReconModule
from app.recon.crtsh import CrtShModule
from app.recon.dns_records import DnsModule
from app.recon.github_dorks import GithubDorksModule
from app.recon.http_fingerprint import HttpModule
from app.recon.shodan_dns import ShodanModule
from app.recon.tls_cert import TlsModule
from app.recon.wayback import WaybackModule
from app.recon.whois_rdap import WhoisModule

MODULES: list[ReconModule] = [
    DnsModule(),
    WhoisModule(),
    CrtShModule(),
    TlsModule(),
    HttpModule(),
    WaybackModule(),
    ShodanModule(),
    GithubDorksModule(),
]

MODULES_BY_NAME: dict[str, ReconModule] = {m.name: m for m in MODULES}


def get_module(name: str) -> ReconModule:
    try:
        return MODULES_BY_NAME[name]
    except KeyError as e:
        raise KeyError(f"unknown recon module: {name}") from e
