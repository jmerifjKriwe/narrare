"""Detection engine for the HTTPx cross-catch regression guard (dual-httpx regime).

Split from ``test_httpx_cross_catch_guard.py`` for the RULE-04 file-size
limit (mirrors ``_storyboard_support.py`` / ``_interview_draft_fakes.py``):
the test module keeps the clean-baseline ratchets and mutation proofs, this
module keeps the detection engine. Still test-tree, not production code
(``tests/`` is outside pyright's CI ``include``, see ``pyproject.toml``).

The repo runs a dual-httpx regime (introduced with the pydantic-ai 2.x bump
in ``42eca2ea``): ``httpx`` (0.x) is used for the project's own REST calls
(models.dev catalog, provider listing), while the bundled SDKs (``openai``
≥3, ``anthropic`` ≥1, ``pydantic-ai`` ≥2) consume ``httpx2`` internally.
Silent-miss risks:

1. **Cross-catch**: an SDK-importing module catching ``httpx.HTTPError``
   (0.x) around an SDK call would silently never fire — the SDK raises
   ``httpx2`` exceptions.  Rule 1 is AST-based: the SDK-module classifier
   honours real ``ast.Import``/``ast.ImportFrom`` statements of
   ``openai``/``anthropic``/``pydantic_ai`` only (docstring or comment
   mentions are prose, not imports), and the catch detector resolves the
   names each module actually binds to ``httpx`` (0.x): module aliases
   (``import httpx`` → ``httpx``, ``import httpx as hx`` → ``hx``) and
   from-import aliases (``from httpx import X [as Y]`` → ``Y``; star
   imports bind nothing).  A handler is flagged when its ``except`` type is
   (a) an attribute of a bound module alias (``except hx.HTTPError:``),
   (b) a bound from-import alias (``except HTTPError:``), or (c) a tuple
   containing either (``except (hx.HTTPError, ValueError):``); the finding
   cites the ``except`` line.  Plain ``except`` and ``except*``
   exception-group handlers are both walked (``ast.Try`` and
   ``ast.TryStar``).  ``httpx2`` never matches because its module name
   differs, and files that fail to parse are skipped, not flagged.
2. **Cross-injection**: an ``http_client=`` argument fed with a client
   constructed from ``httpx`` (0.x) would hand a 0.x client to an SDK
   expecting httpx2.  Rule 2 sweeps ``http_client=`` call sites and flags
   any file where a bare-module ``httpx.(Async)Client(…)`` construction
   exists alongside the call (same-file heuristic — the documented sound
   approximation).

Known-legal own-REST modules (``model_listing.py``,
``models_dev_source.py``) are pinned via ``_KNOWN_OWN_REST_MODULES``: they
import ``httpx`` (0.x) but must never appear in the SDK-importing set.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Rule 1 SDK roots: a module counts as "SDK-importing" when a real import
# statement (ast.Import / ast.ImportFrom) references one of these top-level
# packages.  Docstring or comment mentions are prose and do not count.
_SDK_ROOTS = ("openai", "anthropic", "pydantic_ai")

# Rule 2: http_client= call sites + bare-module client construction.
_HTTP_CLIENT_ARG_RE = re.compile(r"http_client\s*=")
_BARE_HTTPX_CLIENT_CONSTRUCTION_RE = re.compile(r"\bhttpx\.(?:Async)?Client\s*\(")

# Rule 1 scope per brief (prod tree only). Rule 2 additionally scans tests/ so
# that ALL http_client= call sites (the known one lives in tests/) are asserted.
_RULE1_ROOTS = ("packages", "apps", "scripts")
_RULE2_ROOTS = ("packages", "apps", "scripts", "tests")

_KNOWN_OWN_REST_MODULES = (
    "packages/core/narrare_core/llm/model_listing.py",
    "packages/core/narrare_core/llm/models_dev_source.py",
)


def _python_files(root: Path, scan_roots: tuple[str, ...]) -> list[Path]:
    """Collect all ``*.py`` files below the given scan roots."""
    files: list[Path] = []
    for scan_root in scan_roots:
        base = root / scan_root
        if base.is_dir():
            files.extend(sorted(base.rglob("*.py")))
    return files


def _module_violations(
    files: list[Path],
    root: Path,
    offender_re: re.Pattern[str],
    guard_re: re.Pattern[str],
    label: str,
) -> list[str]:
    """Return findings for files matching ``guard_re`` whose lines hit ``offender_re``."""
    findings: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if not guard_re.search(text):
            continue
        for match in offender_re.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            findings.append(f"{label}: {path.relative_to(root)}:{line_no}")
    return findings


def _parse_module(path: Path) -> ast.Module | None:
    """Parse ``path`` with ``ast``; unparseable files are skipped, not flagged.

    ``ValueError`` covers undecodable sources and null-byte files that
    ``ast.parse`` rejects before parsing proper.
    """
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError, ValueError:
        return None


def _parsed_trees(root: Path, scan_roots: tuple[str, ...]) -> list[tuple[Path, ast.Module]]:
    """Parse every candidate file once; skip files that do not parse."""
    trees: list[tuple[Path, ast.Module]] = []
    for path in _python_files(root, scan_roots):
        tree = _parse_module(path)
        if tree is not None:
            trees.append((path, tree))
    return trees


def _imports_sdk_root(tree: ast.Module) -> bool:
    """True when any real import statement references an SDK root package.

    Covers plain and aliased imports (``import openai``, ``import openai as o``,
    dotted names like ``import pydantic_ai.models``) as well as from-imports
    (``from anthropic import …``).  Relative imports (level > 0) reference
    project-internal modules and never the SDK roots.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".", 1)[0] in _SDK_ROOTS for alias in node.names):
                return True
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module is not None
            and node.module.split(".", 1)[0] in _SDK_ROOTS
        ):
            return True
    return False


def _find_sdk_modules(root: Path, scan_roots: tuple[str, ...] = _RULE1_ROOTS) -> set[Path]:
    """Derive the SDK-importing module set from real ``ast`` import statements."""
    return {path for path, tree in _parsed_trees(root, scan_roots) if _imports_sdk_root(tree)}


def _httpx_bindings(tree: ast.Module) -> tuple[set[str], set[str]]:
    """Names bound to ``httpx`` (0.x) anywhere in the module, as two sets.

    Module aliases: ``import httpx`` → ``httpx``, ``import httpx as hx`` → ``hx``.
    From-import aliases: ``from httpx import X [as Y]`` → ``Y`` (a star import
    binds no name and is ignored).  ``httpx2`` never matches because its
    module name differs.
    """
    module_aliases: set[str] = set()
    from_import_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "httpx":
                    module_aliases.add(alias.asname or "httpx")
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module == "httpx":
            for alias in node.names:
                if alias.name != "*":
                    from_import_aliases.add(alias.asname or alias.name)
    return module_aliases, from_import_aliases


def _catches_httpx_binding(
    handler_type: ast.expr,
    module_aliases: set[str],
    from_import_aliases: set[str],
) -> bool:
    """True when an ``except`` type expression references an httpx (0.x) binding.

    Attribute form (``except hx.HTTPError:`` / ``except httpx.HTTPError:``),
    bare-name form (``except HTTPError:`` after a from-import), and tuples
    containing either (``except (hx.HTTPError, ValueError):``).
    """
    exprs = handler_type.elts if isinstance(handler_type, ast.Tuple) else [handler_type]
    for expr in exprs:
        if isinstance(expr, ast.Name) and expr.id in from_import_aliases:
            return True
        if (
            isinstance(expr, ast.Attribute)
            and isinstance(expr.value, ast.Name)
            and expr.value.id in module_aliases
        ):
            return True
    return False


def _find_cross_catch_violations(root: Path) -> list[str]:
    """Rule 1: httpx (0.x) exception catches inside SDK-importing modules (AST-based).

    Both bind forms are covered: attribute access (``except httpx.HTTPError:``,
    ``except hx.HTTPError:``) and from-import aliases (``except HTTPError:`` /
    ``except (HTTPError, …):``), for plain and ``except*`` exception-group
    handlers alike (``ast.Try`` and ``ast.TryStar``).  Findings cite the
    ``except`` line.
    """
    findings: list[str] = []
    for path, tree in _parsed_trees(root, _RULE1_ROOTS):
        if not _imports_sdk_root(tree):
            continue
        module_aliases, from_import_aliases = _httpx_bindings(tree)
        if not module_aliases and not from_import_aliases:
            continue
        linenos: list[int] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Try, ast.TryStar)):
                continue
            for handler in node.handlers:
                if handler.type is None:
                    continue  # Bare `except:` catches nothing httpx-specific.
                if _catches_httpx_binding(handler.type, module_aliases, from_import_aliases):
                    linenos.append(handler.lineno)
        for lineno in sorted(linenos):
            findings.append(f"cross-catch: {path.relative_to(root)}:{lineno}")
    return findings


def _find_http_client_violations(root: Path, *, exclude: tuple[Path, ...] = ()) -> list[str]:
    """Rule 2: httpx-0.x-constructed clients fed into ``http_client=`` (same-file heuristic).

    ``exclude`` removes files from the sweep. The guard test excludes its own
    path because its mutation fixtures contain matching literals by design;
    it also excludes this engine module defensively (currently a no-op — the
    engine's prose does not match the offender regex) so neither guard file
    can flag its own sweep (governance-sweep convention).
    """
    excluded = {p.resolve() for p in exclude}
    files = [
        p
        for p in _python_files(root, _RULE2_ROOTS)
        if p.resolve() not in excluded and _HTTP_CLIENT_ARG_RE.search(p.read_text(encoding="utf-8"))
    ]
    return _module_violations(
        files,
        root,
        _BARE_HTTPX_CLIENT_CONSTRUCTION_RE,
        _HTTP_CLIENT_ARG_RE,
        "http_client-injection",
    )
