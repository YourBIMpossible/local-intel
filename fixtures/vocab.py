"""Deterministic vocabulary for fixture generation.

No clock, no OS randomness, no network. Every identifier is produced by
index from fixed word lists, so the same fixture index always yields the
same token. This is what lets the manifest pin a content hash that survives
regeneration on another machine.
"""

from __future__ import annotations

DOMAINS = [
    "invoice", "ledger", "tenant", "shipment", "catalog", "pricing", "roster",
    "manifest", "warehouse", "contract", "settlement", "payout", "subscription",
    "entitlement", "workspace", "audit", "dispatch", "carrier", "customs",
    "reconcile", "forecast", "allocation", "rebate", "surcharge", "tariff",
]

ACTIONS = [
    "create", "update", "delete", "sync", "export", "import", "validate",
    "resolve", "expand", "collapse", "merge", "split", "archive", "restore",
    "publish", "revoke", "renew", "escalate", "settle", "reconcile",
]

QUALIFIERS = [
    "empty", "partial", "nested", "legacy", "utf8", "bulk", "single", "stale",
    "future", "backdated", "multi_currency", "zero_qty", "negative", "rounded",
    "truncated", "unicode", "boundary", "overlapping", "duplicate", "sparse",
]

MODULES = [
    "core", "api", "domain", "adapters", "persistence", "messaging", "billing",
    "identity", "reporting", "integration", "scheduling", "workflow",
]

TYPE_NAMES = [
    "InvoiceLine", "TenantRef", "ShipmentLeg", "PriceBand", "AuditEntry",
    "CarrierCode", "SettlementBatch", "EntitlementGrant", "WorkspaceId",
    "AllocationKey", "RebateTier", "TariffCode", "CustomsDeclaration",
    "PayoutSchedule", "ContractTerm", "ForecastWindow", "DispatchSlot",
]

FIELD_NAMES = [
    "OriginSystem", "EffectiveFrom", "SettlementRef", "CarrierAlias",
    "TenantScope", "LineDiscriminator", "TaxJurisdiction", "SourceLedger",
    "ParentAllocation", "RebateBasis", "DeclaredValue", "TransitMode",
]


def _pick(words: list[str], i: int) -> str:
    return words[i % len(words)]


def test_slug(i: int) -> str:
    """Stable, unique-per-index, realistic test-case identifier.

    Deliberately free of digit runs: the worker view's grouping signature
    collapses digits as volatile noise, so a numeric suffix would merge
    cases that are genuinely distinct and understate the corpus.
    """
    d = _pick(DOMAINS, i)
    a = _pick(ACTIONS, i // len(DOMAINS))
    q = _pick(QUALIFIERS, i // (len(DOMAINS) * len(ACTIONS)))
    tail = _alpha_suffix(i // (len(DOMAINS) * len(ACTIONS) * len(QUALIFIERS)))
    return f"{d}_{a}_{q}{tail}"


def _alpha_suffix(n: int) -> str:
    if n == 0:
        return ""
    letters = ""
    n -= 1
    while True:
        letters = chr(ord("a") + (n % 26)) + letters
        n = n // 26 - 1
        if n < 0:
            break
    return "_" + letters


def module_path(i: int, ext: str = "py") -> str:
    m = _pick(MODULES, i)
    d = _pick(DOMAINS, i // len(MODULES))
    return f"src/{m}/{d}.{ext}"


def test_path(i: int) -> str:
    m = _pick(MODULES, i)
    return f"tests/{m}/test_{_pick(DOMAINS, i // len(MODULES))}.py"


def type_name(i: int) -> str:
    return _pick(TYPE_NAMES, i)


def field_name(i: int) -> str:
    return _pick(FIELD_NAMES, i)
