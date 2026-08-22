"""Deterministic worker-view builder (§7).

Implements, at Phase-0-minimal fidelity:
  1. Preserve packet metadata / command / environment header.
  2. Deterministically group and deduplicate repeated error material.
  3. Preserve the first occurrence of each group with its original line ID.
  4. If oversized: retain a prefix/suffix budget split, insert explicit
     omission markers with original line ranges for whatever is dropped.
  5. Serialize canonically and compute a worker-view hash.

The grouping heuristic (`normalize_line`) is a v1 implementation choice,
not a quality claim — its recall property is what Phase 1a's
`compressor_primary_evidence_recall` gate (§7, §12) measures. A grouping
signature that under- or over-merges lines is exactly the kind of finding
that gate exists to catch; nothing here should be read as pre-judging it.

Token counting (`estimate_tokens`) is a deterministic chars/4 approximation
for Phase 0 sizing only, not a real tokenizer. Token-based gates in §12/§13
need a real tokenizer before they can be evaluated against this module's
output.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from local_intel.packet import EvidencePacket

WORKER_VIEW_BUILDER_VERSION = "v1"
TRUNCATION_STRATEGY_VERSION = "v1"

_DIGIT_RUN = re.compile(r"\d+")
_HEX_TOKEN = re.compile(r"\b0x[0-9a-fA-F]+\b")
_TIMESTAMP = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
)
_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


def normalize_line(line: str) -> str:
    """Grouping signature: collapse volatile tokens (timestamps, hex
    addresses, uuids, digit runs) so structurally-identical repeated lines
    share a signature regardless of the specific numbers involved."""
    s = line.strip()
    s = _TIMESTAMP.sub("<ts>", s)
    s = _UUID.sub("<uuid>", s)
    s = _HEX_TOKEN.sub("<hex>", s)
    s = _DIGIT_RUN.sub("#", s)
    return s


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


@dataclass(frozen=True)
class WorkerViewConfig:
    version: str = "v1"
    target_input_tokens: int = 24000
    reserve_output_tokens: int = 1800
    retained_prefix_ratio: float = 0.10
    retained_suffix_ratio: float = 0.90

    @property
    def content_budget_tokens(self) -> int:
        return max(0, self.target_input_tokens - self.reserve_output_tokens)


@dataclass
class ErrorGroup:
    signature: str
    first_line_no: int
    first_line_text: str
    source_id: str
    occurrence_line_nos: list[int] = field(default_factory=list)

    @property
    def occurrence_count(self) -> int:
        return len(self.occurrence_line_nos)


@dataclass(frozen=True)
class WorkerView:
    serialized_text: str
    worker_view_hash: str
    packet_content_hash: str
    packet_builder_version: str
    worker_view_builder_version: str
    truncation_strategy_version: str
    serialized_size_chars: int
    configured_num_ctx: int
    max_output_tokens: int
    estimated_input_tokens: int
    truncated: bool
    group_count: int
    deduplicated_occurrence_count: int

    def provenance(self) -> dict[str, Any]:
        """Required worker-view provenance fields (§7)."""
        return {
            "packet_content_hash": self.packet_content_hash,
            "packet_builder_version": self.packet_builder_version,
            "worker_view_builder_version": self.worker_view_builder_version,
            "truncation_strategy_version": self.truncation_strategy_version,
            "worker_view_hash": self.worker_view_hash,
            "configured_num_ctx": self.configured_num_ctx,
            "max_output_tokens": self.max_output_tokens,
        }


def _group_errors(packet: EvidencePacket) -> list[ErrorGroup]:
    groups: dict[str, ErrorGroup] = {}
    for idx, raw_line in enumerate(packet.lines):
        line_no = idx + 1  # 1-indexed original line ID
        sig = normalize_line(raw_line)
        group = groups.get(sig)
        if group is None:
            group = ErrorGroup(
                signature=sig,
                first_line_no=line_no,
                first_line_text=raw_line,
                source_id=packet.source_id,
            )
            groups[sig] = group
        group.occurrence_line_nos.append(line_no)
    return sorted(groups.values(), key=lambda g: g.first_line_no)


def _render_header(packet: EvidencePacket) -> str:
    env_lines = "\n".join(f"  {k}: {v}" for k, v in sorted(packet.environment.items()))
    return (
        "# packet metadata\n"
        f"source_id: {packet.source_id}\n"
        f"kind: {packet.kind}\n"
        f"command: {packet.command}\n"
        f"environment:\n{env_lines}\n"
        f"line_count: {packet.line_count}\n"
    )


def _render_group_entry(group: ErrorGroup) -> str:
    repeats = group.occurrence_count - 1
    tag = (
        f" [+{repeats} repeat(s), lines "
        f"{group.occurrence_line_nos[1]}-{group.occurrence_line_nos[-1]}]"
        if repeats > 0
        else ""
    )
    return f"{group.source_id}:{group.first_line_no}: {group.first_line_text}{tag}"


def _omission_marker(source_id: str, start_line: int, end_line: int) -> str:
    return f"[... omitted {source_id} lines {start_line}-{end_line} ...]"


def build_worker_view(
    packet: EvidencePacket,
    config: WorkerViewConfig | None = None,
    configured_num_ctx: int = 32768,
    max_output_tokens: int = 1800,
) -> WorkerView:
    config = config or WorkerViewConfig()
    header = _render_header(packet)
    groups = _group_errors(packet)
    entries = [_render_group_entry(g) for g in groups]
    body = "\n".join(entries)

    full_text = header + "\n" + body
    budget = config.content_budget_tokens
    truncated = False

    if estimate_tokens(full_text) > budget:
        truncated = True

        # §7 step 4: 10% of the budget for prefix/environment context, 90%
        # for trailing/terminal failures. The prefix share covers the header
        # AND the earliest groups -- not the header alone. Spending it on the
        # header only would discard whatever the header does not use and,
        # worse, would delete the head of the log entirely, which is exactly
        # where a root cause announced once at startup lives.
        prefix_budget_tokens = max(1, int(budget * config.retained_prefix_ratio))
        suffix_budget_tokens = max(1, budget - prefix_budget_tokens)

        header_text = header
        header_tokens = estimate_tokens(header_text)
        if header_tokens > prefix_budget_tokens:
            header_text = header_text[: prefix_budget_tokens * 4]
            header_tokens = estimate_tokens(header_text)

        # Fill the remaining prefix share with the earliest groups.
        prefix_entries: list[str] = []
        prefix_tokens = 0
        prefix_end = 0  # exclusive index into `entries`
        for i, entry in enumerate(entries):
            entry_tokens = estimate_tokens(entry)
            if header_tokens + prefix_tokens + entry_tokens > prefix_budget_tokens:
                break
            prefix_entries.append(entry)
            prefix_tokens += entry_tokens
            prefix_end = i + 1

        # Fill the suffix share with the latest groups, walking backwards.
        suffix_entries: list[str] = []
        suffix_tokens = 0
        suffix_start = len(entries)  # inclusive index into `entries`
        for i in range(len(entries) - 1, prefix_end - 1, -1):
            entry_tokens = estimate_tokens(entries[i])
            if suffix_tokens + entry_tokens > suffix_budget_tokens:
                break
            suffix_entries.append(entries[i])
            suffix_tokens += entry_tokens
            suffix_start = i
        suffix_entries.reverse()

        parts = list(prefix_entries)
        if suffix_start > prefix_end:
            omitted_groups = groups[prefix_end:suffix_start]
            first_line = omitted_groups[0].first_line_no
            last_line = omitted_groups[-1].occurrence_line_nos[-1]
            parts.append(_omission_marker(packet.source_id, first_line, last_line))
        parts.extend(suffix_entries)

        full_text = header_text + "\n" + "\n".join(parts)

    worker_view_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()

    return WorkerView(
        serialized_text=full_text,
        worker_view_hash=worker_view_hash,
        packet_content_hash=packet.content_hash(),
        packet_builder_version=packet.packet_builder_version,
        worker_view_builder_version=WORKER_VIEW_BUILDER_VERSION,
        truncation_strategy_version=TRUNCATION_STRATEGY_VERSION,
        serialized_size_chars=len(full_text),
        configured_num_ctx=configured_num_ctx,
        max_output_tokens=max_output_tokens,
        estimated_input_tokens=estimate_tokens(full_text),
        truncated=truncated,
        group_count=len(groups),
        deduplicated_occurrence_count=sum(g.occurrence_count - 1 for g in groups),
    )
