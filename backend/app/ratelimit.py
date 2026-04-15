"""Shared slowapi Limiter. Keyed by client IP; backed by in-memory by default.

For a real deployment behind a proxy, front the app with a reverse proxy that
sets X-Forwarded-For and trust it via uvicorn's --proxy-headers flag.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])
