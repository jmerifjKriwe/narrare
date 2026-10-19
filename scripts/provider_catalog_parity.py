"""Provider-catalog parity gate: the hand-written Core surfaces vs the catalog.

This is the parity half of ``scripts/generate_provider_catalog.py``, extracted
into its own module for the RULE-04 ``scripts/`` size limit (the generator keeps
the catalog loader, :class:`~scripts.generate_provider_catalog.ProviderSpec`,
both renderers and ``--check``). ``--check`` calls :func:`check_parity` from
here.

Parity is **AST-based**: every surface file is read and parsed with :mod:`ast`
and *never* imported, so the pre-commit hook stays fast and independent of the
venv's optional extras (ADR-099). :func:`check_parity` is a pure function of
``(specs, repo_root)``; it returns one :class:`ParityViolation` per missing or
disagreeing fact, sorted by ``(surface, detail)`` so the output is stable.

The dependency runs one way: the generator imports this module at run time, and
this module imports ``ProviderSpec`` from the generator for **typing only**
(``TYPE_CHECKING``), so no import cycle exists at run time.
"""

from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pathlib import Path

    from scripts.generate_provider_catalog import ProviderSpec

# The catalog's pricing rate keys, shared with the generator's ``pricing_default``
# validator. They live here because the parity gate cannot import the generator.
PRICING_KEYS: tuple[str, ...] = ("input", "output")


@dataclass(frozen=True)
class ParityViolation:
    """One missing or disagreeing provider fact on a hand-written surface."""

    surface: str
    detail: str


def _parse(path: Path) -> ast.Module:
    """Parse a surface module without importing it — the hook must stay cheap."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _value(module: ast.Module, name: str) -> ast.expr | None:
    """Return the value of the module-level ``name = ...`` assignment."""
    for node in module.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                return node.value
    return None


def _literal(path: Path, name: str) -> object | None:
    """Evaluate a module-level literal assignment; ``None`` when it is not one."""
    node = _value(_parse(path), name)
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except ValueError, TypeError:
        return None


def _check_pricing(specs: list[ProviderSpec], repo_root: Path) -> list[ParityViolation]:
    """``DEFAULT_RATES`` names every catalog provider with matching rates."""
    pk, pv = "pricing.keys", "pricing.values"
    rates = _literal(repo_root / "packages/core/narrare_core/llm/model_pricing.py", "DEFAULT_RATES")
    if not isinstance(rates, dict):
        return [ParityViolation(pk, "DEFAULT_RATES is not a literal mapping")]
    table = cast("dict[str, dict[str, float]]", rates)
    catalog = {spec.id: spec.pricing_default for spec in specs}
    violations: list[ParityViolation] = []
    for provider in catalog:
        if provider not in table:
            violations.append(ParityViolation(pk, f"{provider}: missing from DEFAULT_RATES"))
    for provider in table:
        if provider not in catalog:
            violations.append(ParityViolation(pk, f"{provider}: extra in DEFAULT_RATES"))
    for provider, expected in catalog.items():
        actual = table.get(provider, {})
        for key in PRICING_KEYS:
            if key not in actual:
                violations.append(
                    ParityViolation(pv, f"{provider}: no {key} rate (catalog {expected[key]:g})")
                )
            elif float(actual[key]) != expected[key]:
                violations.append(
                    ParityViolation(
                        pv,
                        f"{provider}: catalog {key} {expected[key]:g} != "
                        f"DEFAULT_RATES {actual[key]:g}",
                    )
                )
    return violations


# (case index, provider ids, wildcard, return-value node)
_Arm = tuple[int, tuple[str, ...], bool, ast.expr | None]


def _pattern_ids(pattern: ast.pattern) -> tuple[tuple[str, ...], bool]:
    """The provider literals named by a pattern, and whether it is ``_``."""
    if (
        isinstance(pattern, ast.MatchValue)
        and isinstance(pattern.value, ast.Constant)
        and isinstance(pattern.value.value, str)
    ):
        return (pattern.value.value,), False
    if isinstance(pattern, ast.MatchOr):
        parts = [_pattern_ids(subpattern) for subpattern in pattern.patterns]
        return tuple(pid for ids, _ in parts for pid in ids), any(w for _, w in parts)
    return (), isinstance(pattern, ast.MatchAs) and pattern.pattern is None


def _return_value(case: ast.match_case) -> ast.expr | None:
    return next((stmt.value for stmt in case.body if isinstance(stmt, ast.Return)), None)


def _find_match(module: ast.Module, name: str) -> ast.Match | None:
    """The first ``match`` inside the named module-level function."""
    function = next(
        (node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == name),
        None,
    )
    walk = () if function is None else ast.walk(function)
    return next((child for child in walk if isinstance(child, ast.Match)), None)


def _check_cache(specs: list[ProviderSpec], repo_root: Path) -> list[ParityViolation]:
    """Every provider has exactly one reachable arm whose body matches its policy."""
    cb = "cache.bodies"
    module = _parse(repo_root / "packages/core/narrare_core/llm/_providers/cache_settings.py")
    match = _find_match(module, "build_model_settings")
    arms: list[_Arm] = []
    if match is not None:
        arms = [(i, *_pattern_ids(c.pattern), _return_value(c)) for i, c in enumerate(match.cases)]
    counts = Counter(provider for arm in arms for provider in arm[1])
    wildcard = next((arm[0] for arm in arms if arm[2]), None)
    violations: list[ParityViolation] = []
    for spec in specs:
        count = counts[spec.id]
        if count == 0:
            violations.append(ParityViolation("cache.arms", f"{spec.id}: no match arm"))
        elif count > 1:
            violations.append(ParityViolation("cache.arms", f"{spec.id}: {count} match arms"))
        if wildcard is not None:
            violations += [
                ParityViolation("cache.arms", f"{spec.id}: shadowed by the wildcard arm")
                for arm in arms
                if spec.id in arm[1] and arm[0] > wildcard
            ]
        expected: dict[str, object] = (
            {"cache_control": True} if spec.cache_policy == "anthropic_cache_control" else {}
        )
        for arm in arms:
            if spec.id not in arm[1]:
                continue
            try:
                mapping: object = ast.literal_eval(arm[3]) if arm[3] is not None else None
            except ValueError, TypeError:
                mapping = None
            if not isinstance(mapping, dict):
                violations.append(ParityViolation(cb, f"{spec.id}: body is not a mapping"))
            elif mapping != expected:
                violations.append(
                    ParityViolation(
                        cb, f"{spec.id}: {spec.cache_policy!r} expects {expected!r} != {mapping!r}"
                    )
                )
    return violations


def _check_mem0(specs: list[ProviderSpec], repo_root: Path) -> list[ParityViolation]:
    """``_PROVIDER_DEFAULT_MODELS`` is non-empty and keys are catalog providers."""
    table = _literal(
        repo_root / "packages/core/narrare_core/memory/mem0_client.py", "_PROVIDER_DEFAULT_MODELS"
    )
    if not isinstance(table, dict):
        return [ParityViolation("mem0.keys", "_PROVIDER_DEFAULT_MODELS is not a literal mapping")]
    keys = list(cast("dict[str, object]", table))
    catalog_ids = {spec.id for spec in specs}
    violations = [] if keys else [ParityViolation("mem0.keys", "_PROVIDER_DEFAULT_MODELS is empty")]
    violations += [
        ParityViolation("mem0.keys", f"{key}: not a catalog provider id")
        for key in keys
        if key not in catalog_ids
    ]
    return violations


def _check_prefixes(specs: list[ProviderSpec], repo_root: Path) -> list[ParityViolation]:
    """Every catalog provider appears as a provider in ``_PROVIDER_PREFIXES``."""
    entries = _literal(
        repo_root / "packages/core/narrare_core/llm/_providers/registry.py", "_PROVIDER_PREFIXES"
    )
    pairs = cast("list[tuple[str, str]]", entries) if isinstance(entries, list) else []
    covered = {provider for _, provider in pairs}
    return [
        ParityViolation("prefixes.cover", f"{spec.id}: no entry in _PROVIDER_PREFIXES maps to it")
        for spec in specs
        if spec.id not in covered
    ]


def check_parity(specs: list[ProviderSpec], repo_root: Path) -> list[ParityViolation]:
    """Check the hand-written Core surfaces against the catalog (AST only).

    One violation per missing or disagreeing fact, ordered by surface then
    provider, so the pre-commit output is stable.
    """
    violations = [
        *_check_pricing(specs, repo_root),
        *_check_cache(specs, repo_root),
        *_check_mem0(specs, repo_root),
        *_check_prefixes(specs, repo_root),
    ]
    return sorted(violations, key=lambda violation: (violation.surface, violation.detail))
