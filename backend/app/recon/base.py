"""Recon module contract.

Every recon module is an independent unit of work: given a domain, emit zero or
more findings. Modules are run in parallel by the worker, so they MUST NOT
share mutable state. They receive a `Context` with an `emit` callback that
persists a finding immediately — this is what lets the UI stream results as
they land rather than waiting for the whole scan to finish.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from app.models.finding import Severity


@dataclass
class FindingDraft:
    module: str
    title: str
    severity: Severity = Severity.info
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Context:
    domain: str
    scan_id: uuid.UUID
    emit: Callable[[FindingDraft], None]


class ReconModule(Protocol):
    name: str
    passive: bool  # True = no packets to target; False = active (gated later)

    def run(self, ctx: Context) -> None: ...
