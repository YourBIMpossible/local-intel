"""Deterministic redaction pass (§11).

Redaction is part of reproducibility, not a courtesy step: the protocol
requires that the same source under the same redaction configuration
produces the same redacted fixture, and that a redaction change creates a
new fixture version and batch boundary.

These fixtures are synthetic, so the pass has nothing genuinely sensitive to
remove. It runs anyway, and its hashes are recorded, so that the fixture
pipeline is the same one real logs would travel through -- a redaction step
introduced later, only when it first matters, is a step that has never been
tested on the day it is first relied upon.
"""

from __future__ import annotations

import hashlib
import re

REDACTION_POLICY_VERSION = "v1"
REDACTION_TOOL_VERSION = "v1"

# Ordered: earlier patterns win. Email must precede the generic-token rule so
# an address is not partially consumed by it.
_RULES: list[tuple[str, re.Pattern[str], str]] = [
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "<redacted:email>"),
    (
        "ipv4",
        re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        "<redacted:ipv4>",
    ),
    (
        "uuid",
        re.compile(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
        ),
        "<redacted:uuid>",
    ),
    (
        "bearer_token",
        re.compile(r"\b(?:Bearer|token|api[_-]?key)[=:\s]+[A-Za-z0-9._\-]{12,}", re.I),
        "<redacted:credential>",
    ),
    (
        "windows_user_path",
        re.compile(r"[A-Za-z]:\\Users\\[^\\\s\"']+", re.I),
        r"<redacted:userpath>",
    ),
    (
        "posix_home_path",
        re.compile(r"/(?:home|Users)/[^/\s\"']+"),
        "<redacted:userpath>",
    ),
]


def redact_text(text: str) -> tuple[str, dict[str, int]]:
    """Apply every rule. Returns the redacted text and per-rule hit counts,
    so a fixture with zero hits is visibly zero-hit rather than merely
    assumed clean."""
    counts: dict[str, int] = {}
    out = text
    for name, pattern, replacement in _RULES:
        out, n = pattern.subn(replacement, out)
        counts[name] = n
    return out, counts


def redact_lines(lines: list[str]) -> tuple[list[str], dict[str, int]]:
    joined = "\n".join(lines)
    redacted, counts = redact_text(joined)
    return redacted.split("\n"), counts


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def redaction_identity(input_text: str, output_text: str) -> dict[str, str]:
    """The four §11 redaction provenance fields."""
    return {
        "redaction_policy_version": REDACTION_POLICY_VERSION,
        "redaction_tool_version": REDACTION_TOOL_VERSION,
        "redaction_input_hash": content_hash(input_text),
        "redaction_output_hash": content_hash(output_text),
    }
