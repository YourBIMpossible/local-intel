from pathlib import Path

from local_intel.redact_paths import HOME_TOKEN, contains_local_path, redact_local_paths


def test_single_backslash_users_path_redacted():
    text = r"time=... source=C:\Users\someone\AppData\Local\Ollama\server.log"
    out = redact_local_paths(text)
    assert "someone" not in out
    assert out == f"time=... source={HOME_TOKEN}\\AppData\\Local\\Ollama\\server.log"


def test_json_escaped_double_backslash_path_redacted():
    text = '{"model_store_path": "C:\\\\Users\\\\someone\\\\.ollama\\\\models"}'
    out = redact_local_paths(text)
    assert "someone" not in out
    assert out.startswith('{"model_store_path": "' + HOME_TOKEN)


def test_forward_slash_path_redacted():
    assert "someone" not in redact_local_paths("D:/Users/someone/x/y.gguf")


def test_actual_home_directory_redacted_in_all_spellings():
    home = str(Path.home())
    if not home or home in ("/", "\\"):
        return  # nothing to redact on this platform
    for spelling in (home, home.replace("\\", "\\\\"), home.replace("\\", "/")):
        out = redact_local_paths(f"path={spelling}\\sub\\file")
        assert home.split("\\")[-1] not in out or HOME_TOKEN in out
        assert HOME_TOKEN in out


def test_hardware_facts_are_not_redacted():
    text = "NVIDIA GeForce RTX 5080, 16303 MiB, AMD Ryzen 9, 64 GB, port 11434"
    assert redact_local_paths(text) == text


def test_contains_local_path():
    assert contains_local_path(r"C:\Users\someone\x")
    assert not contains_local_path(r"C:\Program Files\Ollama\ollama.exe")
    assert not contains_local_path(f"{HOME_TOKEN}\\x")


def test_idempotent():
    once = redact_local_paths(r"C:\Users\someone\a C:\Users\other\b")
    assert once == redact_local_paths(once)
    assert once.count(HOME_TOKEN) == 2
