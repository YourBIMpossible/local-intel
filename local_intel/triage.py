"""`local-intel triage-log`: packet -> worker view -> model -> validated artifact.

This is the Phase 0 end-to-end path (§18 Phase 0 steps 2-3). It composes the
deterministic worker-view builder, the bounded Ollama invocation, and the
hard validator, and returns everything needed to record an evaluation event.

It does NOT present anything to Claude. Presentation is a Phase 1b concern
(§5, §12): Phase 1a admission permits advisory use in flagged evaluation
sessions only, and nothing here authorizes that.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from local_intel import __version__
from local_intel.artifact import ARTIFACT_SCHEMA, SCHEMA_VERSION, schema_hash
from local_intel.config_identity import (
    GenerationParameters,
    InvocationConfiguration,
)
from local_intel.ollama_client import InvocationTelemetry, invoke
from local_intel.packet import EvidencePacket
from local_intel.prompt import (
    PROMPT_VERSION,
    WORKER_ID,
    WORKER_VERSION,
    build_prompt,
    prompt_template_text,
)
from local_intel.validator import VALIDATOR_VERSION, ValidationResult, validate_artifact
from local_intel.worker_view import (
    TRUNCATION_STRATEGY_VERSION,
    WORKER_VIEW_BUILDER_VERSION,
    WorkerView,
    WorkerViewConfig,
    build_worker_view,
)

EVIDENCE_PACKET_VERSION = "v1"
# Generous char budget for check 6; the real constraint is num_predict.
MAX_ARTIFACT_CHARS = 8000


@dataclass
class TriageOutcome:
    """One complete invocation record. `presentable` is the only field that
    answers "may this be shown to Claude", and it is true only when the
    model produced output AND every §8 check passed."""

    presentable: bool
    artifact: Any | None
    worker_view: WorkerView
    telemetry: InvocationTelemetry
    validation: ValidationResult | None
    invocation_configuration_id: str
    invocation_failure_kind: str | None
    error: str | None
    raw_text: str | None

    @property
    def structurally_valid(self) -> bool:
        """§6/§12 structural-validity metric: did we get a schema-valid,
        in-contract artifact at all. Distinct from `presentable` only in
        that it is the number the Phase 0 gate counts."""
        return self.presentable


def triage_log(
    packet: EvidencePacket,
    *,
    model_tag: str,
    model_digest: str,
    hardware_profile_id: str,
    ollama_version: str,
    generation: GenerationParameters | None = None,
    view_config: WorkerViewConfig | None = None,
    timeout_ms: int = 120_000,
    keep_alive: str = "5m",
    model_load_state: str = "warm",
) -> TriageOutcome:
    generation = generation or GenerationParameters()
    view_config = view_config or WorkerViewConfig()

    view = build_worker_view(
        packet,
        view_config,
        configured_num_ctx=generation.num_ctx,
        max_output_tokens=generation.max_output_tokens,
    )

    config = InvocationConfiguration(
        worker_id=WORKER_ID,
        worker_version=WORKER_VERSION,
        provider="ollama",
        model_tag=model_tag,
        model_digest=model_digest,
        prompt_text=prompt_template_text(),
        schema_hash=schema_hash(),
        schema_version=SCHEMA_VERSION,
        validator_version=VALIDATOR_VERSION,
        evidence_packet_version=EVIDENCE_PACKET_VERSION,
        packet_builder_version=packet.packet_builder_version,
        worker_view_builder_version=WORKER_VIEW_BUILDER_VERSION,
        truncation_strategy_version=TRUNCATION_STRATEGY_VERSION,
        generation=generation,
        timeout_ms=timeout_ms,
        keep_alive=keep_alive,
        hardware_profile_id=hardware_profile_id,
        ollama_version=ollama_version,
    )
    config_id = config.invocation_configuration_id()

    result = invoke(
        model_tag=model_tag,
        prompt=build_prompt(view.serialized_text),
        schema=ARTIFACT_SCHEMA,
        generation=generation,
        timeout_ms=timeout_ms,
        keep_alive=keep_alive,
        model_load_state=model_load_state,
    )

    if not result.ok:
        return TriageOutcome(
            presentable=False,
            artifact=None,
            worker_view=view,
            telemetry=result.telemetry,
            validation=None,
            invocation_configuration_id=config_id,
            invocation_failure_kind=result.failure_kind,
            error=result.error,
            raw_text=result.raw_text,
        )

    validation = validate_artifact(
        result.parsed,
        authorized_source_ids={packet.source_id},
        packet_line_count=packet.line_count,
        provenance=view.provenance(),
        # The host asserts the authority class; the model is never asked to
        # self-declare it (law 7: workers cannot expand their own authority).
        authority_class="DERIVED",
        max_output_chars=MAX_ARTIFACT_CHARS,
    )

    return TriageOutcome(
        presentable=validation.ok,
        artifact=result.parsed if validation.ok else None,
        worker_view=view,
        telemetry=result.telemetry,
        validation=validation,
        invocation_configuration_id=config_id,
        invocation_failure_kind=None,
        error=None,
        raw_text=result.raw_text,
    )


def local_intel_version() -> str:
    return __version__
