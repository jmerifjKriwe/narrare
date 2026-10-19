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
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from scripts.generate_provider_catalog import ProviderSpec

# The catalog's pricing rate keys, shared with the generator's ``pricing_default``
# validator. They live here because the parity gate cannot import the generator.
PRICING_KEYS: tuple[str, ...] = ("input", "output")

_SETTINGS = Path("packages/core/narrare_core/settings.py")
"""The operator settings module; ``CoreSettings`` holds the provider key fields."""

_PROVIDER_SERVICE = Path("apps/api/narrare/setup/provider_service.py")
"""The setup-phase provider service: the fallback catalog and the test call."""

_I18N_DIR = Path("packages/i18n/messages")
"""Where the message-file trees live; the file stem is the key's first segment."""

_LOCALES: tuple[str, ...] = ("en", "de", "fr")
"""Every locale a catalog ``label_key`` must resolve in (RULE-16)."""


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


def _class_annotations(module: ast.Module, name: str) -> dict[str, ast.expr | None] | None:
    """The annotated field names of the module-level class ``name``.

    Each value is the assignment's right-hand side — the ``Field(...)`` call for
    an aliased field, ``None`` for a bare annotation. ``None`` is returned when
    the class itself is absent, so a caller can tell "no such class" from "a
    class without annotated fields"; both are reported, never ignored.
    """
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            fields: dict[str, ast.expr | None] = {}
            for statement in node.body:
                if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                    fields[statement.target.id] = statement.value
            return fields
    return None


def _env_var(field_name: str, value: ast.expr | None) -> str | None:
    """The env var a settings field reads.

    A declared ``validation_alias`` (then ``alias``) wins: that is the name
    pydantic-settings looks up. Without one the env var is the upper-cased field
    name, ``SettingsConfigDict``'s default. ``None`` means the field declares an
    alias that is not a string literal, so the env var is *unknown* — the caller
    reports that rather than assuming the default name.
    """
    if not isinstance(value, ast.Call):
        return field_name.upper()
    for keyword_name in ("validation_alias", "alias"):
        declared = next(
            (keyword for keyword in value.keywords if keyword.arg == keyword_name), None
        )
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
        env_var = _env_var(spec.settings_field, fields[spec.settings_field])
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
            problems.append("**: _FALLBACK_MODELS unpacks another mapping")
            continue
        provider = _provider_member(key)
        if provider is None:
            problems.append(f"{ast.unparse(key)}: is not an AIProvider.<MEMBER> key")
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
    """The providers ``_test_call`` compares against ``AIProvider``.

    ``_test_call`` is an async *method* of ``ProviderService``, so the search
    walks the whole module and accepts both function node types; searching only
    ``module.body`` for a plain ``def`` would have missed it and reported a
    rename that never happened.

    ``None`` when the function is absent, so a renamed or deleted test call is a
    violation for every affected provider rather than a silent pass.
    """
    module = _parse(repo_root / _PROVIDER_SERVICE)
    function = next(
        (
            node
            for node in ast.walk(module)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "_test_call"
        ),
        None,
    )
    if function is None:
        return None
    providers: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Compare):
            continue
        for operand in [node.left, *node.comparators]:
            provider = _provider_member(operand)
            if provider is not None:
                providers.add(provider)
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


def _load_messages(path: Path) -> tuple[dict[str, object] | None, str]:
    """Parse a message file; the reason is ``""`` when it parsed.

    A missing file, a decode error and a non-object document each come back as a
    reason, never as an empty-but-valid mapping: the caller turns every reason
    into a violation.
    """
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        return None, f"cannot be read ({error.strerror or error})"
    except ValueError as error:
        return None, f"is not valid UTF-8 JSON ({error})"
    if not isinstance(raw, dict):
        return None, "is not a JSON object"
    return cast("dict[str, object]", raw), ""


def _contains(messages: dict[str, object], path: list[str]) -> bool:
    """Whether the nested ``path`` holds a value in a parsed message file.

    Only the segments before the last must be mappings; the leaf holds the
    label, and a ``null`` label counts as absent (it is not a translatable
    string). Each step re-checks the runtime shape and hands the walk on through
    an ``object``, so a non-mapping document cannot be mistaken for a hit.
    """
    node: object = messages
    for part in path:
        if not isinstance(node, dict):
            return False
        child: object = dict(node).get(part)
        if child is None:
            return False
        node = child
    return True


def _check_labels(specs: list[ProviderSpec], repo_root: Path) -> list[ParityViolation]:
    """Every catalog ``label_key`` resolves in every locale (RULE-16)."""
    ll = "labels.locales"
    violations: list[ParityViolation] = []
    loaded: dict[Path, tuple[dict[str, object] | None, str]] = {}
    for spec in specs:
        stem, separator, nested = spec.label_key.partition(".")
        if not stem or not separator or not nested:
            violations.append(
                ParityViolation(
                    ll, f"{spec.id}: label_key {spec.label_key} is not a <file>.<path> key"
                )
            )
            continue
        for locale in _LOCALES:
            relative = _I18N_DIR / locale / f"{stem}.json"
            if relative not in loaded:
                loaded[relative] = _load_messages(repo_root / relative)
            messages, reason = loaded[relative]
            if messages is None:
                violations.append(ParityViolation(ll, f"{spec.id}: {relative} {reason}"))
            elif not _contains(messages, nested.split(".")):
                violations.append(
                    ParityViolation(ll, f"{spec.id}: {spec.label_key} missing in {relative}")
                )
    return violations


def check_parity(specs: list[ProviderSpec], repo_root: Path) -> list[ParityViolation]:
    """Check the hand-written Core surfaces against the catalog (AST only).

    One violation per missing or disagreeing fact, ordered by surface then
    provider, so the pre-commit output is stable.

    Every checker fails **loud**: when its anchor (a class, a dict literal, a
    function, a message file) is absent, renamed or of an unexpected shape, it
    reports violations naming the affected providers instead of returning an
    empty list — a silent pass would read as coverage the gate does not have.
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
