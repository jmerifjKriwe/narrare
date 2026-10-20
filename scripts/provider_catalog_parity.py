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
from pathlib import Path
from typing import TYPE_CHECKING, cast

from scripts.provider_catalog_parity_i18n import check_labels

if TYPE_CHECKING:
    from scripts.generate_provider_catalog import ProviderSpec

# The catalog's pricing rate keys, shared with the generator's ``pricing_default``
# validator. They live here because the parity gate cannot import the generator.
PRICING_KEYS: tuple[str, ...] = ("input", "output")

_SETTINGS = Path("packages/core/narrare_core/settings.py")
"""The operator settings module; ``CoreSettings`` holds the provider key fields."""

_PROVIDER_SERVICE = Path("apps/api/narrare/setup/provider_service.py")
"""The setup-phase provider service: the fallback catalog and the test call."""


@dataclass(frozen=True)
class ParityViolation:
    """One missing or disagreeing provider fact on a hand-written surface."""

    surface: str
    detail: str


def _parse(path: Path) -> ast.Module:
    """Parse a surface module without importing it — the hook must stay cheap."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _value(module: ast.Module, name: str) -> ast.expr | None:
    """The value of the **last** module-level ``name = ...`` binding.

    Runtime last-wins: a later binding shadows an earlier one, and a bare
    annotation binds nothing, so it does not reset the value.
    """
    found: ast.expr | None = None
    for node in module.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if node.value is not None and any(
            isinstance(target, ast.Name) and target.id == name for target in targets
        ):
            found = node.value
    return found


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
    table = cast("dict[str, dict[str, object]]", rates)
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
                continue
            rate = actual[key]
            if not isinstance(rate, (int, float)) or isinstance(rate, bool):
                violations.append(
                    ParityViolation(pv, f"{provider}: {key} is {type(rate).__name__}, not a number")
                )
            elif float(rate) != expected[key]:
                violations.append(
                    ParityViolation(
                        pv,
                        f"{provider}: catalog {key} {expected[key]:g} != DEFAULT_RATES {rate:g}",
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
    """Every catalog provider appears as a provider in ``_PROVIDER_PREFIXES``.

    A non-list anchor is **one** structural violation naming the anchor, not one
    "no entry" detail per provider. Malformed elements are skipped for coverage
    and reported by their own structural violation, so they never raise.
    """
    pc = "prefixes.cover"
    entries = _literal(
        repo_root / "packages/core/narrare_core/llm/_providers/registry.py", "_PROVIDER_PREFIXES"
    )
    if not isinstance(entries, list):
        return [
            ParityViolation(pc, f"_PROVIDER_PREFIXES must be a list, got {type(entries).__name__}")
        ]
    covered: set[str] = set()
    violations: list[ParityViolation] = []
    for entry in cast("list[object]", entries):
        elements = cast("tuple[object, ...]", entry) if isinstance(entry, tuple) else ()
        prefix, provider = elements if len(elements) == 2 else (None, None)
        if isinstance(prefix, str) and isinstance(provider, str):
            covered.add(provider)
        else:
            violations.append(ParityViolation(pc, f"{entry!r}: not a (prefix, provider) pair"))
    violations += [
        ParityViolation(pc, f"{spec.id}: no entry in _PROVIDER_PREFIXES maps to it")
        for spec in specs
        if spec.id not in covered
    ]
    return violations


def _class_annotations(
    module: ast.Module, name: str
) -> dict[str, tuple[ast.expr, ast.expr | None]] | None:
    """The annotated fields of the module-level class ``name``.

    Values are ``(annotation, assignment)`` so an alias in either place is seen.
    ``None`` means the class is absent; the caller reports that, never ignores it.
    """
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            fields: dict[str, tuple[ast.expr, ast.expr | None]] = {}
            for statement in node.body:
                if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                    fields[statement.target.id] = (statement.annotation, statement.value)
            return fields
    return None


def _field_call(annotation: ast.expr, value: ast.expr | None) -> ast.Call | None:
    """The ``Field(...)`` call a field declares, on the value or in ``Annotated``."""
    for candidate in (value, annotation):
        if isinstance(candidate, ast.Call):
            return candidate
        if isinstance(candidate, ast.Subscript):
            elements = (
                candidate.slice.elts
                if isinstance(candidate.slice, ast.Tuple)
                else [candidate.slice]
            )
            for element in elements:
                if (
                    isinstance(element, ast.Call)
                    and isinstance(element.func, ast.Name)
                    and element.func.id == "Field"
                ):
                    return element
    return None


def _env_var(field_name: str, annotation: ast.expr, value: ast.expr | None) -> str | None:
    """The env var a settings field reads.

    ``validation_alias`` (then ``alias``) wins on a ``Field(...)`` assignment or
    ``Annotated`` metadata; otherwise the upper-cased field name. ``None`` means
    a declared alias is not a string literal, so the name is unknown.
    """
    call = _field_call(annotation, value)
    if call is None:
        return field_name.upper()
    for keyword_name in ("validation_alias", "alias"):
        declared = next((keyword for keyword in call.keywords if keyword.arg == keyword_name), None)
        if declared is None:
            continue
        if isinstance(declared.value, ast.Constant) and isinstance(declared.value.value, str):
            return declared.value.value
        return None
    return field_name.upper()


def _check_settings(specs: list[ProviderSpec], repo_root: Path) -> list[ParityViolation]:
    """Every catalog ``settings_field`` is declared and reads its ``api_key_env``."""
    sf = "settings.fields"
    fields = _class_annotations(_parse(repo_root / _SETTINGS), "CoreSettings")
    violations: list[ParityViolation] = []
    for spec in specs:
        if spec.settings_field is None:
            continue
        if fields is None:
            violations.append(
                ParityViolation(sf, f"{spec.id}: CoreSettings is missing from {_SETTINGS}")
            )
            continue
        if spec.settings_field not in fields:
            violations.append(
                ParityViolation(
                    sf, f"{spec.id}: {spec.settings_field} is not declared in CoreSettings"
                )
            )
            continue
        env_var = _env_var(spec.settings_field, *fields[spec.settings_field])
        if env_var is None:
            violations.append(
                ParityViolation(
                    sf,
                    f"{spec.id}: {spec.settings_field} declares an alias this gate cannot evaluate",
                )
            )
        elif env_var != spec.api_key_env:
            violations.append(
                ParityViolation(
                    sf,
                    f"{spec.id}: {spec.settings_field} reads {env_var}"
                    f" != catalog {spec.api_key_env}",
                )
            )
    return violations


def _check_api_keys(specs: list[ProviderSpec], repo_root: Path) -> list[ParityViolation]:
    """Every non-null ``api_key_env`` has a declared ``CoreSettings`` field.

    This is the *existence* half; :func:`_check_settings` owns whether that field
    reads the same env var, so a wrong alias is reported once, by one surface.
    """
    ak = "apikeys.cover"
    fields = _class_annotations(_parse(repo_root / _SETTINGS), "CoreSettings")
    violations: list[ParityViolation] = []
    for spec in specs:
        if spec.api_key_env is None:
            continue
        if spec.settings_field is None:
            violations.append(
                ParityViolation(
                    ak, f"{spec.id}: {spec.api_key_env} has no settings_field in the catalog"
                )
            )
        elif fields is None or spec.settings_field not in fields:
            violations.append(
                ParityViolation(
                    ak, f"{spec.id}: no declared CoreSettings field named {spec.settings_field}"
                )
            )
    return violations


def _provider_member(node: ast.expr) -> str | None:
    """The provider id of an ``AIProvider.<MEMBER>`` expression, else ``None``."""
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "AIProvider"
    ):
        return node.attr.lower()
    return None


def _fallback_entries(repo_root: Path) -> tuple[dict[str, ast.expr], list[str]] | None:
    """``_FALLBACK_MODELS`` as provider id → value node, plus its unparsed keys.

    ``None`` means the assignment is absent or is not a dict literal; the keys
    that are not ``AIProvider.<MEMBER>`` are returned as ready-made problem
    strings so the caller reports them instead of dropping them.
    """
    node = _value(_parse(repo_root / _PROVIDER_SERVICE), "_FALLBACK_MODELS")
    if not isinstance(node, ast.Dict):
        return None
    entries: dict[str, ast.expr] = {}
    problems: list[str] = []
    for key, value in zip(node.keys, node.values, strict=True):
        if key is None:
            problems.append("_FALLBACK_MODELS: '**' unpacking leaves its keys unverified")
            continue
        provider = _provider_member(key)
        if provider is None:
            problems.append(f"_FALLBACK_MODELS key {ast.unparse(key)!r} is not AIProvider.<MEMBER>")
        elif provider in entries:
            problems.append(f"{provider}: duplicate key in _FALLBACK_MODELS")
        else:
            entries[provider] = value
    return entries, problems


def _model_ids(node: ast.expr) -> list[str] | None:
    """The ``id=`` strings of a ``[ProviderModel(...), ...]`` list.

    ``None`` when the value is not that shape (a call, a different constructor,
    a non-literal ``id``), so a list this gate cannot fully read is reported
    rather than compared against a truncated set.
    """
    if not isinstance(node, ast.List):
        return None
    model_ids: list[str] = []
    for element in node.elts:
        if not isinstance(element, ast.Call) or not isinstance(element.func, ast.Name):
            return None
        if element.func.id != "ProviderModel":
            return None
        declared = next((keyword for keyword in element.keywords if keyword.arg == "id"), None)
        if declared is None:
            return None
        if not (isinstance(declared.value, ast.Constant) and isinstance(declared.value.value, str)):
            return None
        model_ids.append(declared.value.value)
    return model_ids


def _check_fallbacks(specs: list[ProviderSpec], repo_root: Path) -> list[ParityViolation]:
    """``_FALLBACK_MODELS`` covers exactly the catalog ids with the catalog models."""
    fk, fi = "fallback.keys", "fallback.ids"
    parsed = _fallback_entries(repo_root)
    if parsed is None:
        return [
            ParityViolation(
                fk,
                f"{spec.id}: _FALLBACK_MODELS is not a dict literal in {_PROVIDER_SERVICE}",
            )
            for spec in specs
        ]
    entries, problems = parsed
    catalog = {spec.id for spec in specs}
    violations = [ParityViolation(fk, problem) for problem in problems]
    violations += [
        ParityViolation(fk, f"{spec.id}: missing from _FALLBACK_MODELS")
        for spec in specs
        if spec.id not in entries
    ]
    violations += [
        ParityViolation(fk, f"{provider}: extra in _FALLBACK_MODELS")
        for provider in entries
        if provider not in catalog
    ]
    for spec in specs:
        if spec.id not in entries:
            continue
        expected = list(spec.fallback_models)
        actual = _model_ids(entries[spec.id])
        if actual is None:
            violations.append(
                ParityViolation(
                    fi, f"{spec.id}: fallback list is not a list of ProviderModel(id=...)"
                )
            )
        elif actual != expected:
            violations.append(
                ParityViolation(fi, f"{spec.id}: catalog {expected} != _FALLBACK_MODELS {actual}")
            )
    return violations


def _test_call_providers(repo_root: Path) -> set[str] | None:
    """The providers ``ProviderService._test_call`` branches on.

    Only the class's own ``_test_call`` counts, and only ``if``/``if``-expression
    tests are read: a nested helper, lambda, comprehension filter, ``assert`` or
    earlier look-alike cannot satisfy the gate. ``None`` when the class or method
    is absent, so a rename is loud, not a silent pass.
    """
    module = _parse(repo_root / _PROVIDER_SERVICE)
    service = next(
        (
            node
            for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == "ProviderService"
        ),
        None,
    )
    function = next(
        (
            node
            for node in (service.body if service is not None else [])
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "_test_call"
        ),
        None,
    )
    if function is None:
        return None
    providers: set[str] = set()
    stack: list[ast.AST] = list(function.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, (ast.If, ast.IfExp)):
            providers.update(
                provider
                for comparison in ast.walk(node.test)
                if isinstance(comparison, ast.Compare)
                for operand in [comparison.left, *comparison.comparators]
                if (provider := _provider_member(operand)) is not None
            )
        stack.extend(ast.iter_child_nodes(node))
    return providers


def _check_test_call(specs: list[ProviderSpec], repo_root: Path) -> list[ParityViolation]:
    """Every ``requires_endpoint_selector`` provider has a ``_test_call`` branch."""
    tc = "testcall.endpoints"
    providers = _test_call_providers(repo_root)
    violations: list[ParityViolation] = []
    for spec in specs:
        if not spec.requires_endpoint_selector:
            continue
        if providers is None:
            violations.append(
                ParityViolation(tc, f"{spec.id}: _test_call is missing from {_PROVIDER_SERVICE}")
            )
        elif spec.id not in providers:
            violations.append(
                ParityViolation(
                    tc, f"{spec.id}: no branch in _test_call handles its endpoint selector"
                )
            )
    return violations


def _check_labels(specs: list[ProviderSpec], repo_root: Path) -> list[ParityViolation]:
    """Wrap the i18n module's ``(surface, detail)`` pairs as violations."""
    return [ParityViolation(surface, detail) for surface, detail in check_labels(specs, repo_root)]


def check_parity(specs: list[ProviderSpec], repo_root: Path) -> list[ParityViolation]:
    """Check the hand-written Core surfaces against the catalog (AST only).

    One violation per missing or disagreeing fact, ordered by surface then
    provider, so the pre-commit output is stable.

    Every checker fails **loud**: an absent, renamed or malformed anchor reports
    violations instead of an empty list — a silent pass would read as coverage
    the gate does not have. Provider facts name the provider; structural facts
    name the offending anchor or key, because no provider owns them.
    """
    violations = [
        *_check_pricing(specs, repo_root),
        *_check_cache(specs, repo_root),
        *_check_mem0(specs, repo_root),
        *_check_prefixes(specs, repo_root),
        *_check_settings(specs, repo_root),
        *_check_api_keys(specs, repo_root),
        *_check_fallbacks(specs, repo_root),
        *_check_test_call(specs, repo_root),
        *_check_labels(specs, repo_root),
    ]
    return sorted(violations, key=lambda violation: (violation.surface, violation.detail))
