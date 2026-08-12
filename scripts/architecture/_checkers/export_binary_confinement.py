"""RULE-08 · Export render-binary confinement (ADR-081).

Each production render binary (``typst``, ``pandoc``) may be spawned ONLY
inside its renderer adapter module. This AST checker enforces that
mechanically in CI from the first subprocess call — not deferred to review
(D6).

Matches the existing per-file AST checker pattern (see ``llm.py`` / RULE-01b):
the checker is wired into :func:`scripts.architecture._checkers.scan_file` and
``"RULE-08"`` is added to the ``ENFORCED_RULES`` self-report in
``scripts/check_architecture.py``.

Design
------
AST-based, not grep. The checker builds an import-alias map per file so that
aliased imports (``import subprocess as sp`` → ``sp.run``;
``from asyncio import create_subprocess_exec as cspe`` → ``cspe``) resolve
correctly. It flags any ``ast.Call`` whose resolved target is a subprocess
spawn entry point AND whose argv contains the string-literal ``"typst"`` or
``"pandoc"``.

Tracked spawn entry points (resolved through aliases):

    subprocess.run / Popen / call / check_call / check_output
    asyncio.create_subprocess_exec / create_subprocess_shell
    os.system / os.popen        (belt-and-braces against shell invocation)

EPUBCheck is deliberately **out of scope**: it is CI-only (invoked from the
``tests/golden/export/`` harness, never from production), so confining it to a
renderer adapter would be wrong.

Limitation (documented honestly)
--------------------------------
Dynamic binary-name construction (e.g. ``subprocess.run(["typ" + "st"])`` or
a name read from a variable) is NOT caught — the AST cannot statically resolve
it. This is an accepted trade-off: the production renderers always invoke the
binary via a string literal, and a deliberately evasive author is a personnel
problem, not an architecture-rule problem. The confinement is a guardrail
against accidental drift, not a sandbox.
"""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.architecture.helpers import compute_type_checking_lines
from scripts.architecture.types import Violation

# ── Tracked spawn entry points ────────────────────────────────────────────
# module → the call attributes we flag (resolved through import aliases).
_MODULE_SPAWN_ATTRS: dict[str, set[str]] = {
    "subprocess": {"run", "Popen", "call", "check_call", "check_output"},
    "asyncio": {"create_subprocess_exec", "create_subprocess_shell"},
    "os": {"system", "popen"},
}

# Fully-qualified dangerous targets: {"subprocess.run", "asyncio...", ...}
_DANGEROUS_TARGETS: frozenset[str] = frozenset(
    f"{mod}.{attr}" for mod, attrs in _MODULE_SPAWN_ATTRS.items() for attr in attrs
)

# Entry points whose argv is a single shell command string → substring match
# (the binary name is embedded in the command, e.g. ``os.system("typst ...")``).
# Exec-style entry points use an exact-match on the discrete binary-name token.
_SHELL_ENTRY_POINTS: frozenset[str] = frozenset(
    {"asyncio.create_subprocess_shell", "os.system", "os.popen"}
)

# The two production render binaries. EPUBCheck is CI-only and out of scope.
FLAGGED_BINARIES: tuple[str, ...] = ("typst", "pandoc")


# ── Alias map ────────────────────────────────────────────────────────────
def _build_alias_map(
    tree: ast.AST,
) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    """Build import-alias maps from a module's AST.

    Returns ``(module_aliases, name_aliases)``:

    - ``module_aliases`` maps a local module name to its real module name::

          import subprocess          → {"subprocess": "subprocess"}
          import subprocess as sp    → {"sp": "subprocess"}
          import asyncio as aio      → {"aio": "asyncio"}

    - ``name_aliases`` maps a directly-imported name to ``(module, attr)``::

          from subprocess import run
              → {"run": ("subprocess", "run")}
          from asyncio import create_subprocess_exec as cspe
              → {"cspe": ("asyncio", "create_subprocess_exec")}
    """
    module_aliases: dict[str, str] = {}
    name_aliases: dict[str, tuple[str, str]] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # ``import a.b`` binds the name "a" (top-level); Typst-style
                # dotted names are rare here — record the full dotted name.
                local = alias.asname or alias.name.split(".")[0]
                real = alias.name
                module_aliases[local] = real
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            for alias in node.names:
                local = alias.asname or alias.name
                name_aliases[local] = (node.module, alias.name)
    return module_aliases, name_aliases


# ── Call resolution ──────────────────────────────────────────────────────
def _resolve_call_target(
    call: ast.Call,
    module_aliases: dict[str, str],
    name_aliases: dict[str, tuple[str, str]],
) -> str | None:
    """Resolve a ``Call`` node's function to a ``module.attr`` string, or None.

    Handles both invocation forms:

    - ``subprocess.run(...)`` / ``sp.run(...)``  — Attribute on an (aliased) module
    - ``run(...)`` / ``cspe(...)``               — a directly-imported name
    """
    func = call.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        local_module = func.value.id
        if local_module in module_aliases:
            real_module = module_aliases[local_module]
            return f"{real_module}.{func.attr}"
    elif isinstance(func, ast.Name):
        local_name = func.id
        if local_name in name_aliases:
            mod, attr = name_aliases[local_name]
            return f"{mod}.{attr}"
    return None


def _argv_string_literals(call: ast.Call) -> list[str]:
    """Collect string literals from a spawn call's positional argv.

    Covers both forms:

    - ``subprocess.run(["typst", "compile", ...])`` — leading list literal
    - ``asyncio.create_subprocess_exec("typst", "compile", ...)`` — positional
    """
    literals: list[str] = []
    for arg in call.args:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            literals.append(arg.value)
        elif isinstance(arg, ast.List):
            for elt in arg.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    literals.append(elt.value)
    return literals


def _argv_names_flagged_binary(literals: list[str], is_shell: bool) -> bool:
    """Return True if any string literal references a flagged render binary.

    Exec-style entry points use an exact match on the discrete binary-name
    token; shell-style entry points substring-match (the binary name is
    embedded in the command string).
    """
    for lit in literals:
        for binary in FLAGGED_BINARIES:
            if is_shell:
                if binary in lit:
                    return True
            elif lit == binary:
                return True
    return False


# ── Public checker ───────────────────────────────────────────────────────
def check_export_binary_confinement(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],  # kept for signature parity with sibling checkers
    allowed_modules: list[str],
) -> list[Violation]:
    """RULE-08: typst/pandoc subprocess spawns confined to renderer adapters.

    Args:
        rel_path: file path relative to the project root.
        tree: parsed AST of the file.
        source_lines: the file's source lines (unused — signature parity with
            sibling checkers; the alias map is built from the AST).
        allowed_modules: the renderer-adapter files exempt from confinement
            (``export_binary_allowed_modules`` in pyproject.toml).
    Returns:
        Violations for every unconfined typst/pandoc spawn in this file.
    """
    # Exempt the allowed renderer-adapter files (exact path match, consistent
    # with the llm.py / agent_allowed_modules convention).
    if any(rel_path.startswith(m.rstrip("/")) for m in allowed_modules):
        return []

    tc_lines = compute_type_checking_lines(tree)
    module_aliases, name_aliases = _build_alias_map(tree)

    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if node.lineno in tc_lines:
            continue
        target = _resolve_call_target(node, module_aliases, name_aliases)
        if target is None or target not in _DANGEROUS_TARGETS:
            continue
        literals = _argv_string_literals(node)
        is_shell = target in _SHELL_ENTRY_POINTS
        if _argv_names_flagged_binary(literals, is_shell):
            violations.append(
                Violation(
                    file=Path(rel_path),
                    line=node.lineno,
                    rule="RULE-08",
                    detail=(
                        f"Spawn of render binary via '{target}()' outside its "
                        f"renderer adapter. typst/pandoc may be invoked ONLY "
                        f"inside apps/api/narrare/export/renderers/ "
                        f"(RULE-08 / ADR-081)."
                    ),
                )
            )
    return violations
