"""Five deterministic test-log fixture templates.

Strata (operator-specified, aligned to the §11 corpus stratification):

  repeated_assertion     one assertion failing across many parametrised cases
  compiler_type          a type-check/compile pass failing across many files
  cascade_root_cause     one root cause producing many downstream failures
  multiple_independent   several genuinely unrelated failure clusters
  environment_failure    the harness/environment fails, not the code

Every template is a pure function of its index: no clock, no RNG, no
environment. Line counts are frozen in FIXTURE_SPECS so that regeneration
reproduces byte-identical logs.

IMPORTANT -- these are SYNTHETIC. §6 calls for five representative *real*
test-log packets. Synthetic fixtures reproduce realistic structure and size
but cannot reproduce the messiness of a real failing suite. That deviation
is recorded in the manifest and the smoke report; it is not papered over.
"""

from __future__ import annotations

from dataclasses import dataclass

from fixtures import vocab

# Synthetic timestamps: fixed base, deterministic increments. A clock read
# here would break the reproducibility the manifest hashes depend on.
_BASE_EPOCH_S = 1_700_000_000


def _ts(i: int) -> str:
    """Monotonic pseudo-timestamp. Digit runs are collapsed by the worker
    view's grouping signature, so these never create spurious groups."""
    total = _BASE_EPOCH_S + i * 3
    hh = (total // 3600) % 24
    mm = (total // 60) % 60
    ss = total % 60
    return f"2026-03-14T{hh:02d}:{mm:02d}:{ss:02d}.{(i * 137) % 1000:03d}Z"


def _header(command: str, collected: int, runner: str) -> list[str]:
    return [
        f"$ {command}",
        f"{runner}",
        "platform linux -- Python 3.11.9, pytest-8.2.0, pluggy-1.5.0",
        "rootdir: /srv/build/workspace",
        "plugins: xdist-3.6.1, cov-5.0.0, timeout-2.3.1",
        "timeout: 300.0s",
        f"collected {collected} items",
        "",
    ]


def repeated_assertion(n_cases: int) -> list[str]:
    """One rule fails identically across a large parametrised matrix.

    The failure text is byte-identical every time, so the worker view should
    collapse it to a single group with a large repeat count. Whether it
    actually does is a compressor property the fixture is meant to expose,
    not something the fixture presumes.
    """
    lines = _header(
        "pytest -q tests/validation --timeout=300", 4820, "===== test session starts ====="
    )
    for i in range(n_cases):
        slug = vocab.test_slug(i)
        path = vocab.test_path(i)
        passed = i % 4 != 0
        if passed:
            lines.append(f"{path}::test_rule[{slug}] PASSED")
        else:
            lines.append(f"{path}::test_rule[{slug}] FAILED")
            lines.append("E   AssertionError: rule 'non_negative_total' violated")
            lines.append("E   assert computed_total >= 0")
            lines.append("E    +  where computed_total = normalise(line_items)")
            lines.append("src/domain/rules.py:214: AssertionError")
    lines += [
        "",
        "=========================== short test summary ===========================",
        f"FAILED {n_cases // 4} tests, {n_cases - n_cases // 4} passed",
        "",
        f"===== {n_cases // 4} failed, {n_cases - n_cases // 4} passed in 412.88s =====",
    ]
    return lines


def compiler_type(n_files: int) -> list[str]:
    """A type-check pass failing across many distinct files.

    Each diagnostic is genuinely distinct (file, type, field all vary), so
    this stratum stresses the opposite of dedup: a view that must truncate
    rather than collapse.
    """
    lines = [
        "$ npm run typecheck",
        "> workspace@0.0.0 typecheck",
        "> tsc --noEmit -p tsconfig.build.json",
        "",
    ]
    for i in range(n_files):
        path = vocab.module_path(i, ext="ts")
        want = vocab.type_name(i)
        got = vocab.type_name(i + 7)
        field = vocab.field_name(i)
        col = 5 + (i % 40)
        line_no = 12 + (i % 300)
        lines.append(
            f"{path}({line_no},{col}): error TS2345: Argument of type "
            f"'{got}' is not assignable to parameter of type '{want}'."
        )
        lines.append(
            f"  Property '{field}' is missing in type '{got}' but required in type '{want}'."
        )
        if i % 3 == 0:
            lines.append(
                f"{path}({line_no + 4},{col}): error TS2339: Property '{field}' "
                f"does not exist on type '{got}'."
            )
    lines += ["", f"Found {n_files + n_files // 3} errors in {n_files} files.", ""]
    return lines


def cascade_root_cause(n_downstream: int) -> list[str]:
    """One missing migration; every dependent test fails downstream.

    The root cause appears once, early, and never repeats -- so if the
    worker view's suffix-biased truncation drops the head of the log, the
    adjudicated primary evidence disappears. That is precisely the
    compressor-recall failure mode §7 charges to the builder, and this
    fixture exists to make it visible rather than theoretical.
    """
    lines = _header(
        "pytest -q tests/ --timeout=300", 5140, "===== test session starts ====="
    )
    lines += [
        "tests/conftest.py::session_fixture SETUP",
        "INFO  alembic.runtime.migration  Context impl PostgresqlImpl.",
        "INFO  alembic.runtime.migration  Will assume transactional DDL.",
        "ERROR alembic.runtime.migration  Target database is not up to date.",
        "ERROR conftest: migration 'a7f2_add_origin_system' was never applied",
        "ERROR conftest: relation \"invoice_line\" is missing column \"origin_system\"",
        "WARNING conftest: continuing with degraded schema (--no-strict-schema)",
        "",
    ]
    for i in range(n_downstream):
        slug = vocab.test_slug(i)
        path = vocab.test_path(i)
        if i % 5 == 0:
            lines.append(f"{path}::test_{slug} PASSED")
            continue
        lines.append(f"{path}::test_{slug} FAILED")
        lines.append(
            "E   psycopg2.errors.UndefinedColumn: column "
            '"origin_system" does not exist'
        )
        lines.append(f"E   LINE 1: SELECT invoice_line.origin_system FROM invoice_line")
        lines.append("src/persistence/repository.py:88: UndefinedColumn")
    lines += [
        "",
        "=========================== short test summary ===========================",
        f"===== {n_downstream - n_downstream // 5} failed, {n_downstream // 5} passed in 688.21s =====",
    ]
    return lines


def multiple_independent(n_each: int) -> list[str]:
    """Three unrelated failure clusters interleaved with passing tests.

    Interleaved rather than blocked, because a log that presents each
    cluster as a contiguous run makes the classification easier than any
    real parallel test runner would.
    """
    lines = _header(
        "pytest -q -n 4 tests/ --timeout=300", 6210, "===== test session starts ====="
    )
    clusters = [
        (
            "null_reference",
            "E   AttributeError: 'NoneType' object has no attribute 'settlement_ref'",
            "src/billing/settlement.py:131: AttributeError",
        ),
        (
            "timeout",
            "E   Failed: Timeout >300.0s (call) -- carrier gateway did not respond",
            "src/integration/carrier_gateway.py:57: Timeout",
        ),
        (
            "serialization",
            "E   ValueError: Out of range float values are not JSON compliant: nan",
            "src/reporting/serializer.py:203: ValueError",
        ),
    ]
    for i in range(n_each * 3):
        slug = vocab.test_slug(i)
        path = vocab.test_path(i)
        if i % 3 != 0:
            lines.append(f"[gw{i % 4}] {path}::test_{slug} PASSED")
            continue
        name, detail, frame = clusters[(i // 3) % 3]
        lines.append(f"[gw{i % 4}] {path}::test_{slug} FAILED")
        lines.append(detail)
        lines.append(frame)
    lines += [
        "",
        "=========================== short test summary ===========================",
        "===== 691 failed, 1382 passed in 921.44s =====",
    ]
    return lines


def environment_failure(n_noise: int) -> list[str]:
    """The runner itself dies: disk exhaustion during collection.

    Correct triage here is `environment_or_infrastructure_failure`, and the
    tempting wrong answer -- blaming the code under test -- is present in
    the log as a large volume of plausible-looking downstream noise.
    """
    lines = [
        "$ pytest -q tests/ --timeout=300",
        "===== test session starts =====",
        "platform linux -- Python 3.11.9, pytest-8.2.0, pluggy-1.5.0",
        "rootdir: /srv/build/workspace",
        "",
        "WARNING  runner: available disk space on /srv/build below 512 MiB",
        "ERROR    runner: failed to write .pytest_cache/v/cache/nodeids",
        "ERROR    runner: OSError: [Errno 28] No space left on device",
        "ERROR    runner: coverage database could not be initialised",
        "",
    ]
    for i in range(n_noise):
        slug = vocab.test_slug(i)
        path = vocab.test_path(i)
        if i % 7 == 0:
            lines.append(f"{path}::test_{slug} ERROR")
            lines.append("E   OSError: [Errno 28] No space left on device")
            lines.append("E   during fixture setup: tmp_path_factory")
        else:
            lines.append(f"{path}::test_{slug} ERROR")
            lines.append(
                "E   INTERNALERROR> OSError: [Errno 28] No space left on device"
            )
    lines += [
        "",
        "!!!!! Interrupted: 1 error during collection !!!!!",
        "ERROR runner: session aborted after 44.02s",
    ]
    return lines


@dataclass(frozen=True)
class FixtureSpec:
    fixture_id: str
    stratum: str
    command: str
    builder: str
    size_param: int
    expected_classification: str


# Size params were tuned once so that every fixture's worker view reaches the
# frozen 24,000-token target, then frozen here. They are inputs to a
# deterministic function, so changing one changes that fixture's hash and
# creates a new fixture version (§11).
FIXTURE_SPECS: list[FixtureSpec] = [
    FixtureSpec(
        fixture_id="f01_repeated_assertion",
        stratum="repeated_assertion",
        command="pytest -q tests/validation --timeout=300",
        builder="repeated_assertion",
        size_param=6000,
        expected_classification="cascade_from_single_root_cause",
    ),
    FixtureSpec(
        fixture_id="f02_compiler_type",
        stratum="compiler_type",
        command="npm run typecheck",
        builder="compiler_type",
        size_param=3200,
        expected_classification="multiple_independent_failures",
    ),
    FixtureSpec(
        fixture_id="f03_cascade_root_cause",
        stratum="cascade_root_cause",
        command="pytest -q tests/ --timeout=300",
        builder="cascade_root_cause",
        size_param=4200,
        expected_classification="cascade_from_single_root_cause",
    ),
    FixtureSpec(
        fixture_id="f04_multiple_independent",
        stratum="multiple_independent",
        command="pytest -q -n 4 tests/ --timeout=300",
        builder="multiple_independent",
        size_param=2100,
        expected_classification="multiple_independent_failures",
    ),
    FixtureSpec(
        fixture_id="f05_environment_failure",
        stratum="environment_failure",
        command="pytest -q tests/ --timeout=300",
        builder="environment_failure",
        size_param=3000,
        expected_classification="environment_or_infrastructure_failure",
    ),
]

BUILDERS = {
    "repeated_assertion": repeated_assertion,
    "compiler_type": compiler_type,
    "cascade_root_cause": cascade_root_cause,
    "multiple_independent": multiple_independent,
    "environment_failure": environment_failure,
}
