"""Domain validator is the abuse-gate for the whole platform — it gets tests."""

from __future__ import annotations

import pytest

from app.services.domain_validator import InvalidDomainError, normalize_domain


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("example.com", "example.com"),
        ("  EXAMPLE.com ", "example.com"),
        ("https://example.com/path?q=1", "example.com"),
        ("example.com.", "example.com"),
        ("sub.example.co.uk", "sub.example.co.uk"),
    ],
)
def test_accepts_and_normalizes(raw: str, expected: str) -> None:
    assert normalize_domain(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "localhost",
        "foo.local",
        "bar.internal",
        "thing.lan",
        "127.0.0.1",
        "192.168.1.1",
        "::1",
        "not a domain",
        "nodot",
    ],
)
def test_rejects(raw: str) -> None:
    with pytest.raises(InvalidDomainError):
        normalize_domain(raw)


def test_idn_punycode_conversion() -> None:
    # bücher.de → xn--bcher-kva.de
    assert normalize_domain("bücher.de") == "xn--bcher-kva.de"
