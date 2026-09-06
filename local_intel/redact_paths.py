"""Redact local account paths from text destined for the repository.

Server-log segments, hardware profiles, and result documents carry absolute
Windows paths under the operator's profile directory. Those paths identify
the local account and are not evidence: nothing in the Phase 0 analysis
depends on them. Everything under ``<drive>:\\Users\\<name>`` (single- or
JSON-escaped double-backslash, or forward-slash) is replaced by ``<HOME>``,
as is the literal current home directory in any of those spellings.
"""

from __future__ import annotations

import re
from pathlib import Path

HOME_TOKEN = "<HOME>"

# <drive>:<sep>Users<sep><account>  where <sep> is "\\", "\" or "/".
_USERS_DIR = re.compile(r"[A-Za-z]:(?:\\\\|\\|/)Users(?:\\\\|\\|/)[^\\/\"'\s\]]+")


def _home_spellings() -> list[str]:
    home = str(Path.home())
    if not home or home in ("/", "\\"):
        return []
    variants = {home, home.replace("\\", "\\\\"), home.replace("\\", "/")}
    return sorted(variants, key=len, reverse=True)


def redact_local_paths(text: str) -> str:
    """Return ``text`` with every local account path replaced by ``<HOME>``."""
    out = _USERS_DIR.sub(HOME_TOKEN, text)
    for spelling in _home_spellings():
        out = out.replace(spelling, HOME_TOKEN)
    return out


def contains_local_path(text: str) -> bool:
    """True if ``text`` still carries a path that ``redact_local_paths`` would remove."""
    return redact_local_paths(text) != text
