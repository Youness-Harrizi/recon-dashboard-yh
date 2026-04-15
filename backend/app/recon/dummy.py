"""Placeholder module used to validate the orchestrator end-to-end.

Replaced in phase 5 by real passive-recon modules (dns, whois, crtsh, ...).
"""

from __future__ import annotations

import time

from app.models.finding import Severity
from app.recon.base import Context, FindingDraft


class DummyModule:
    name = "dummy"
    passive = True

    def run(self, ctx: Context) -> None:
        # Emit three findings spread over ~3s so we can see them stream in.
        ctx.emit(
            FindingDraft(
                module=self.name,
                title=f"Dummy finding A for {ctx.domain}",
                severity=Severity.info,
                data={"step": 1, "note": "first finding"},
            )
        )
        time.sleep(1)
        ctx.emit(
            FindingDraft(
                module=self.name,
                title=f"Dummy finding B for {ctx.domain}",
                severity=Severity.low,
                data={"step": 2, "note": "second finding"},
            )
        )
        time.sleep(1)
        ctx.emit(
            FindingDraft(
                module=self.name,
                title=f"Dummy finding C for {ctx.domain}",
                severity=Severity.medium,
                data={"step": 3, "note": "third finding"},
            )
        )
