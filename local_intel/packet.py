"""Minimal EvidencePacket<TestLog> for Phase 0 / Phase 1a use.

This is the Phase 0 "minimal packet-to-worker-view serialization" input
type (§18 Phase 0 step 2). The frozen §9 EvidencePacket contract is a
Phase 1a deliverable (§18 Phase 1a step 1) and may add fields this does
not have; nothing here should be treated as that frozen contract.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvidencePacket:
    source_id: str
    kind: str
    command: str
    environment: dict[str, str] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)
    packet_builder_version: str = "v1"

    @property
    def line_count(self) -> int:
        return len(self.lines)

    def content_hash(self) -> str:
        """Deterministic hash over packet content (§7 packet_content_hash)."""
        canonical = json.dumps(
            {
                "source_id": self.source_id,
                "kind": self.kind,
                "command": self.command,
                "environment": self.environment,
                "lines": self.lines,
            },
            sort_keys=True,
            ensure_ascii=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
