"""Registry invariants. Catches typos and accidental module removal."""

from __future__ import annotations

import pytest

from app.recon.registry import MODULES, MODULES_BY_NAME, get_module

EXPECTED_MODULES = {"dns", "whois", "crtsh", "tls", "http", "wayback", "github"}


def test_all_expected_modules_registered() -> None:
    names = {m.name for m in MODULES}
    assert EXPECTED_MODULES <= names, f"missing: {EXPECTED_MODULES - names}"


def test_names_unique() -> None:
    names = [m.name for m in MODULES]
    assert len(names) == len(set(names))


def test_module_protocol_shape() -> None:
    for m in MODULES:
        assert isinstance(m.name, str) and m.name
        assert isinstance(m.passive, bool)
        assert callable(getattr(m, "run", None))


def test_get_module_roundtrip() -> None:
    for name in EXPECTED_MODULES:
        assert get_module(name) is MODULES_BY_NAME[name]


def test_get_module_raises_on_unknown() -> None:
    with pytest.raises(KeyError):
        get_module("does-not-exist")
