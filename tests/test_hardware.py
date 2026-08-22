import json

import pytest

from local_intel.config_identity import HardwareProfile
from local_intel.hardware import load_profile, write_profile


def _profile(**overrides) -> HardwareProfile:
    base = {
        "machine_profile_id": "test-box",
        "cpu_model": "Test CPU",
        "system_ram_gb": 64.0,
        "gpu_model": "Test GPU",
        "gpu_vram_gb": 16.0,
        "gpu_driver_version": "1.2.3",
        "os_version": "TestOS 1.0",
        "ollama_version": "0.32.14",
        "local_intel_version": "0.1.0",
        "storage_type": "SSD (NVMe)",
        "power_profile": "High performance",
        "cpu_cores": 16,
        "cpu_threads": 32,
        "model_store_path": "/models",
    }
    base.update(overrides)
    return HardwareProfile(**base)


def test_write_then_load_roundtrip(tmp_path):
    profile = _profile()
    write_profile(profile, {"installed_models": []}, ["note"], profile_dir=tmp_path)
    loaded = load_profile("test-box", profile_dir=tmp_path)
    assert loaded["profile"]["cpu_model"] == "Test CPU"
    assert loaded["profile_hash"] == profile.profile_hash()
    assert loaded["notes"] == ["note"]


def test_profile_is_immutable_on_disk(tmp_path):
    """A hardware profile that could be overwritten in place would let
    today's machine silently re-describe yesterday's measurements."""
    write_profile(_profile(), {}, [], profile_dir=tmp_path)
    with pytest.raises(FileExistsError):
        write_profile(_profile(gpu_model="Swapped GPU"), {}, [], profile_dir=tmp_path)


def test_profile_hash_is_content_sensitive():
    assert _profile().profile_hash() != _profile(gpu_vram_gb=24.0).profile_hash()
    assert _profile().profile_hash() == _profile().profile_hash()


def test_committed_profile_has_every_section_six_field():
    """§6 enumerates the fields every batch must record. A profile missing
    one is not a partial record -- it is an unreproducible batch."""
    doc = json.loads(
        (
            __import__("pathlib").Path("hardware_profiles/workstation-zeria-01.json")
        ).read_text(encoding="utf-8")
    )
    required = [
        "machine_profile_id",
        "cpu_model",
        "system_ram_gb",
        "gpu_model",
        "gpu_vram_gb",
        "gpu_driver_version",
        "os_version",
        "ollama_version",
        "local_intel_version",
        "storage_type",
        "power_profile",
    ]
    for field in required:
        assert doc["profile"].get(field) not in (None, ""), f"missing §6 field: {field}"
