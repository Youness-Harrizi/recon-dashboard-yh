"""Normalize and validate a user-supplied domain.

Purpose: prevent the platform from being used to probe internal/private targets
(SSRF / abuse / accidental scans of the host itself). We do NOT resolve DNS here
— that is the module's responsibility — but we reject obviously unsafe inputs.
"""

from __future__ import annotations

import ipaddress
import re

_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)"
    r"(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$"
)

_BLOCKED_SUFFIXES = (
    ".local",
    ".localhost",
    ".internal",
    ".lan",
    ".home",
    ".arpa",
)

_BLOCKED_EXACT = {"localhost"}


class InvalidDomainError(ValueError):
    pass


def normalize_domain(raw: str) -> str:
    """Return the canonical lowercase punycode form, or raise InvalidDomainError."""
    if not raw or not raw.strip():
        raise InvalidDomainError("domain is empty")

    s = raw.strip().lower()

    # Strip common URL prefixes / paths if the user pasted one.
    s = re.sub(r"^https?://", "", s)
    s = s.split("/", 1)[0]
    s = s.split("?", 1)[0]
    s = s.rstrip(".")

    if not s:
        raise InvalidDomainError("domain is empty")

    # Reject IP literals outright — this tool is for domain recon.
    try:
        ip = ipaddress.ip_address(s)
        raise InvalidDomainError(f"IP addresses are not accepted ({ip})")
    except ValueError:
        pass  # not an IP, good

    if s in _BLOCKED_EXACT:
        raise InvalidDomainError(f"'{s}' is not a public domain")

    if any(s == suf.lstrip(".") or s.endswith(suf) for suf in _BLOCKED_SUFFIXES):
        raise InvalidDomainError(f"'{s}' is a reserved/internal TLD")

    # IDN → punycode
    try:
        s = s.encode("idna").decode("ascii")
    except UnicodeError as e:
        raise InvalidDomainError(f"invalid IDN: {e}") from e

    if not _HOSTNAME_RE.match(s):
        raise InvalidDomainError(f"'{s}' is not a valid hostname")

    return s
