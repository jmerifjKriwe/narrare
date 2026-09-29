"""ADR-086 · Prevention gate — no factory-time model resolution in DI wiring.

ADR-086 Review Trigger #1 (plan batch J1): once the migration ledger is
empty, an architecture check must forbid the eager pattern that caused the
400-before-422 / FK-500 defect class — ``await resolver.resolve(...)`` and
``await ....get_resolved_limits(...)`` executing inside dependency-factory
bodies of ``deps*.py`` / ``dependencies*.py`` / ``router*.py`` files under
``apps/api/``.

Sanctioned idiom (allowlist): the awaited call sits inside a nested closure
(an inner ``async def``) and at least one function of its enclosing chain
references ``LazyModelResolution`` — resolution is deferred to first use.

Sanctioned survivors (ratchet): entries listed in the
``adr086_factory_resolution`` section of
``scripts/architecture/ai-gate-baseline.json`` pass, keyed by
``<rel_path>::<enclosing top-level function>`` (line-drift stable). Existing
debt may shrink (prune the entry); any NEW key is a gate violation until
fixed or ADR-approved into the baseline.

Out of scope (by design): ``get_resolved_limits`` in router files is
request-time service delegation (the settings endpoint's product IS the
resolved limits — ADR-086 Implementation Notes); sync ``resolver.resolve``
inside ``LazyModelResolution(lambda: ...)`` is the wiring idiom itself and
is never awaited here.
"""

from __future__ import annotations

import ast
import json
from functools import lru_cache
from pathlib import Path

from scripts.architecture.baselines import DEFAULT_BASELINE_PATH
from scripts.architecture.types import Violation

RULE_ID = "ADR-086"
_BASELINE_SECTION = "adr086_factory_resolution"

_SCAN_ROOT = "apps/api/"

# Factory-file basenames: FastAPI DI providers live here.
_DEPS_PREFIXES = ("deps", "dependencies")
_ROUTER_PREFIXES = ("router",)

_LIMITS_METHOD = "get_resolved_limits"
_LAZY_MARKER = "LazyModelResolution"


def load_factory_resolution_baseline(
    path: Path = DEFAULT_BASELINE_PATH,
) -> frozenset[str]:
    """Load the sanctioned-survivor keys from the ratcheted baseline."""
    if not path.exists():
        return frozenset()
    data = json.loads(path.read_text(encoding="utf-8"))
    section = data.get(_BASELINE_SECTION, [])
    return frozenset(str(item) for item in section)


@lru_cache(maxsize=1)
def _default_baseline() -> frozenset[str]:
    """Cached baseline for scan_file calls (baseline edits need a new process)."""
    return load_factory_resolution_baseline()


def _is_factory_file(basename: str) -> bool:
    """deps*/dependencies* are factory files; router* only guards ``resolve``."""
    return basename.startswith(_DEPS_PREFIXES) or basename.startswith(_ROUTER_PREFIXES)


def _is_routing_resolver(receiver: ast.expr) -> bool:
    """Match the routing-resolution receivers: ``resolver``/``*_resolver``/
    ``model_resolution``. Unrelated ``.resolve(...)`` receivers (pathlib &
    friends) stay out of scope."""
    return isinstance(receiver, ast.Name) and (
        receiver.id == "model_resolution" or receiver.id.endswith("resolver")
    )


def _references_lazy_resolution(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True when the function body references ``LazyModelResolution``."""
    return any(
        (isinstance(node, ast.Name) and node.id == _LAZY_MARKER)
        or (isinstance(node, ast.Attribute) and node.attr == _LAZY_MARKER)
        for node in ast.walk(fn)
    )


def _enclosing_chain(
    tree: ast.AST,
    target: ast.Await,
) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Outermost-to-innermost function defs enclosing ``target``."""
    chain: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    def visit(node: ast.AST, stack: list[ast.FunctionDef | ast.AsyncFunctionDef]) -> bool:
        if node is target:
            chain.extend(stack)
            return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stack.append(node)
            for child in ast.iter_child_nodes(node):
                if visit(child, stack):
                    return True
            stack.pop()
            return any(visit(child, stack) for child in ast.iter_child_nodes(node))
        return any(visit(child, stack) for child in ast.iter_child_nodes(node))

    visit(tree, [])
    return chain


def check_lazy_model_resolution(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
    baseline_keys: frozenset[str] | None = None,
) -> list[Violation]:
    """Flag awaited model resolution in DI-factory bodies (ADR-086).

    Only awaited calls are flagged: a plain (sync) ``resolver.resolve`` is
    the ``LazyModelResolution(lambda: ...)`` wiring idiom. Inside nested
    closures the call is allowed only when the enclosing chain references
    ``LazyModelResolution``; baseline-listed survivors are skipped.
    """
    del source_lines  # AST-local check; kept for checker-signature parity.
    basename = Path(rel_path).name
    if not rel_path.startswith(_SCAN_ROOT) or not _is_factory_file(basename):
        return []
    limits_in_scope = basename.startswith(_DEPS_PREFIXES)

    if baseline_keys is None:
        baseline_keys = _default_baseline()

    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Await) or not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        if not isinstance(func, ast.Attribute):
            continue
        if func.attr == _LIMITS_METHOD:
            if not limits_in_scope:
                continue  # router files: service delegation, not factory wiring
        elif func.attr == "resolve" and _is_routing_resolver(func.value):
            pass
        else:
            continue

        chain = _enclosing_chain(tree, node)
        nested = len(chain) >= 2
        lazy_sanctioned = nested and any(_references_lazy_resolution(fn) for fn in chain)
        if lazy_sanctioned:
            continue

        top_fn = chain[0].name if chain else "<module>"
        key = f"{rel_path}::{top_fn}"
        if key in baseline_keys:
            continue

        violations.append(
            Violation(
                file=Path(rel_path),
                line=node.lineno,
                rule=RULE_ID,
                detail=(
                    f"Factory-time model resolution ({func.attr}) in "
                    f"{top_fn!r} — wire LazyModelResolution and resolve at "
                    f"first use inside a closure (ADR-086); sanctioned "
                    f"survivors need a baseline entry"
                ),
            )
        )
    return violations
