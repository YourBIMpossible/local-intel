import dataclasses

from local_intel.config_identity import GenerationParameters, InvocationConfiguration


def _config(**overrides) -> InvocationConfiguration:
    base = {
        "worker_id": "test_log_triage",
        "worker_version": "0.1.0",
        "provider": "ollama",
        "model_tag": "qwen2.5-coder:14b",
        "model_digest": "9ec8897f747e",
        "prompt_text": "analyse this log",
        "schema_hash": "schemahash",
        "schema_version": "v1",
        "validator_version": "v1",
        "evidence_packet_version": "v1",
        "packet_builder_version": "v1",
        "worker_view_builder_version": "v1",
        "truncation_strategy_version": "v1",
        "generation": GenerationParameters(),
        "timeout_ms": 120_000,
        "keep_alive": "5m",
        "hardware_profile_id": "workstation-1",
        "ollama_version": "0.32.14",
    }
    base.update(overrides)
    return InvocationConfiguration(**base)


def test_identical_configs_share_an_id():
    assert _config().invocation_configuration_id() == _config().invocation_configuration_id()


def test_prompt_change_creates_a_new_configuration():
    a = _config().invocation_configuration_id()
    b = _config(prompt_text="analyse this log differently").invocation_configuration_id()
    assert a != b


def test_generation_parameter_change_creates_a_new_configuration():
    a = _config().invocation_configuration_id()
    b = _config(generation=GenerationParameters(temperature=0.7)).invocation_configuration_id()
    assert a != b


def test_model_digest_change_creates_a_new_configuration():
    a = _config().invocation_configuration_id()
    b = _config(model_digest="deadbeef").invocation_configuration_id()
    assert a != b


def test_hardware_profile_is_part_of_identity():
    a = _config().invocation_configuration_id()
    b = _config(hardware_profile_id="workstation-2").invocation_configuration_id()
    assert a != b


def test_prompt_text_is_stored_as_hash_not_plaintext():
    d = _config().canonical_dict()
    assert "prompt_text" not in d
    assert len(d["prompt_hash"]) == 64


def test_every_config_field_affects_the_id():
    """Law 9: an artifact must be attributable to its COMPLETE invocation
    configuration. A field that does not change the id is a field that can
    silently differ between two runs that claim to be the same batch."""
    baseline = _config()
    baseline_id = baseline.invocation_configuration_id()
    for field in dataclasses.fields(InvocationConfiguration):
        if field.name == "generation":
            continue  # covered separately; nested dataclass
        current = getattr(baseline, field.name)
        mutated = "MUTATED" if not isinstance(current, int) else current + 1
        assert (
            _config(**{field.name: mutated}).invocation_configuration_id() != baseline_id
        ), f"{field.name} does not affect invocation_configuration_id"


def test_greedy_decoding_interpretation_is_stated():
    assert "runtime nondeterminism" in GenerationParameters().decoding_interpretation
    assert "model stability" in GenerationParameters(temperature=0.8).decoding_interpretation
