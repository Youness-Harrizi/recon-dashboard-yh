"""Central registry of enabled recon modules.

Adding a module = import it here and put it in MODULES. The orchestrator reads
this list to fan out work; unit tests use it to assert coverage.
"""

from __future__ import annotations

from app.recon.base import ReconModule
from app.recon.dummy import DummyModule

MODULES: list[ReconModule] = [
    DummyModule(),
]

MODULES_BY_NAME: dict[str, ReconModule] = {m.name: m for m in MODULES}


def get_module(name: str) -> ReconModule:
    try:
        return MODULES_BY_NAME[name]
    except KeyError as e:
        raise KeyError(f"unknown recon module: {name}") from e
