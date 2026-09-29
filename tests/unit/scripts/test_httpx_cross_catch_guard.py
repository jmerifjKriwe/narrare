"""HTTPx cross-catch regression guard for the dual-httpx regime.

The repo runs a dual-httpx regime (introduced with the pydantic-ai 2.x bump in
``42eca2ea``): ``httpx`` (0.x) is used for the project's own REST calls (models.dev
catalog, provider listing), while the bundled SDKs (``openai`` ≥3, ``anthropic`` ≥1,
``pydantic-ai`` ≥2) consume ``httpx2`` internally.  Silent-miss risks:

1. **Cross-catch**: an SDK-importing module catching ``httpx.HTTPError`` (0.x)
   around an SDK call would silently never fire — the SDK raises ``httpx2``
   exceptions.  Rule 1 asserts that no module importing ``openai``/``anthropic``/
   ``pydantic_ai`` contains a bare-module ``except httpx.`` clause
   (``httpx2.`` references are fine and excluded by the ``\\bhttpx\\.`` pattern).
   Both bind forms are covered: attribute access (``except httpx.HTTPError:``)
   and from-import aliases (``from httpx import HTTPError`` followed by
   ``except HTTPError:`` / ``except (HTTPError, …):``), since the from-import
   form hides the module qualifier from the catch line.
2. **Cross-injection**: an ``http_client=`` argument fed with a client constructed
   from ``httpx`` (0.x) would hand a 0.x client to an SDK expecting httpx2.
   Rule 2 sweeps ``http_client=`` call sites and flags any file where a bare-module
   ``httpx.(Async)Client(…)`` construction exists alongside the call (same-file
   heuristic — the documented sound approximation).

Known-legal own-REST modules (``model_listing.py``, ``models_dev_source.py``) are
pinned: they import ``httpx`` (0.x) but must never appear in the SDK-importing set.

Style: governance sweep like the ``doc_drift`` guard tests — clean-baseline
ratchet against the real tree plus tmp-injection mutation proofs.  Self-contained
(single test file, no prod script) and excluded from pyright's CI ``include``
(see ``pyproject.toml``).
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Brief-derived SDK-import signature (rg parity: `import openai|from anthropic|pydantic_ai`).
# Over-inclusive matches (docstring mentions) keep the sweep conservative.
_SDK_IMPORT_RE = re.compile(r"\bimport openai\b|\bfrom anthropic\b|\bpydantic_ai\b")

# Rule 1: bare-module httpx exception clauses. `\bhttpx\.` cannot match inside
# `httpx2.` (the char after `httpx` there is `2`, not `.`).
_BARE_HTTPX_EXCEPT_RE = re.compile(r"^\s*except\b[^\n:]*\bhttpx\.", re.MULTILINE)

# Rule 1b (from-import variant): `from httpx import HTTPError` binds exception
# names as bare locals, so the catch line no longer contains `httpx.` and the
# attribute-access regex above misses it.  The guard resolves such aliases
# module-locally instead.  `\bfrom httpx import\b` cannot match inside
# `from httpx2 import …` (the char after `httpx` there is `2`, not a space).
_HTTPX_FROM_IMPORT_RE = re.compile(r"\bfrom httpx import\b")

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


def _find_sdk_modules(root: Path, scan_roots: tuple[str, ...] = _RULE1_ROOTS) -> set[Path]:
    """Derive the SDK-importing module set (rg-parity heuristic)."""
    return {
        path
        for path in _python_files(root, scan_roots)
        if _SDK_IMPORT_RE.search(path.read_text(encoding="utf-8"))
    }


def _logical_line(text: str, start: int) -> str:
    """Return the logical line starting at ``start``, joining paren continuations.

    Sweep-style folder: consumes lines until parentheses balance (or a non-
    parenthesized line ends), stripping ``#`` comments per line.  String
    literals containing parens are out of heuristic scope (import statements
    bind identifiers, not strings — same documented-approximation style as
    Rule 2's same-file heuristic).
    """
    parts: list[str] = []
    depth = 0
    for line in text[start:].split("\n"):
        code = line.split("#", 1)[0]
        parts.append(code)
        depth += code.count("(") - code.count(")")
        if depth <= 0:
            break
    return " ".join(parts)


def _aliases_imported_from_httpx(text: str) -> set[str]:
    """Local names bound by ``from httpx import …`` statements (alias-aware).

    Covers single-line imports and parenthesized lists — single-line and
    multi-line.  Non-identifier bindings (``import *``) are ignored.
    """
    aliases: set[str] = set()
    for match in _HTTPX_FROM_IMPORT_RE.finditer(text):
        line = _logical_line(text, match.end())
        for part in line.split(","):
            part = part.strip().strip("()").strip()
            if not part:
                continue
            # `HTTPError as HxError` binds the local name HxError.
            name = part.split()[-1] if " as " in part else part
            if name.isidentifier():
                aliases.add(name)
    return aliases


def _find_cross_catch_violations(root: Path) -> list[str]:
    """Rule 1: bare-httpx exception clauses inside SDK-importing modules.

    Covers both bind forms: attribute access (``except httpx.HTTPError:``)
    and from-import aliases (``except HTTPError:`` / ``except (HTTPError, …):``).
    """
    sdk_modules = _find_sdk_modules(root)
    findings = _module_violations(
        sorted(sdk_modules),
        root,
        _BARE_HTTPX_EXCEPT_RE,
        _SDK_IMPORT_RE,
        "cross-catch",
    )
    for path in sorted(sdk_modules):
        text = path.read_text(encoding="utf-8")
        for alias in sorted(_aliases_imported_from_httpx(text)):
            # Bare-name and tuple catch forms both name the alias before the
            # colon, so one line regex covers `except A:` / `except (A, B):`.
            alias_except_re = re.compile(
                rf"^\s*except\b[^:\n]*\b{re.escape(alias)}\b", re.MULTILINE
            )
            for match in alias_except_re.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                findings.append(f"cross-catch: {path.relative_to(root)}:{line_no}")
    return findings


def _find_http_client_violations(root: Path, *, exclude: tuple[Path, ...] = ()) -> list[str]:
    """Rule 2: httpx-0.x-constructed clients fed into ``http_client=`` (same-file heuristic).

    ``exclude`` removes files from the sweep (self-exclusion of this guard file:
    its synthetic fixtures contain matching literals by design and must not flag
    the clean baseline — governance-sweep convention).
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


# ── Clean baseline against the real repo tree ────────────────────


def test_rule1_clean_baseline() -> None:
    """No SDK-importing module catches bare-httpx exceptions (current tree)."""
    violations = _find_cross_catch_violations(_REPO_ROOT)
    assert violations == [], f"bare httpx cross-catch in SDK modules: {violations}"


def test_rule2_clean_baseline() -> None:
    """No http_client= site is fed a bare-httpx-constructed client (current tree)."""
    violations = _find_http_client_violations(_REPO_ROOT, exclude=(Path(__file__),))
    assert violations == [], f"httpx 0.x client injected via http_client=: {violations}"


def test_own_rest_modules_are_not_sdk_modules() -> None:
    """Pairing pin: model_listing/models_dev_source use httpx 0.x for own REST only."""
    sdk_modules = {p.relative_to(_REPO_ROOT).as_posix() for p in _find_sdk_modules(_REPO_ROOT)}
    for rel in _KNOWN_OWN_REST_MODULES:
        module = _REPO_ROOT / rel
        assert module.exists(), f"known own-REST module missing: {rel}"
        assert "import httpx\n" in module.read_text(encoding="utf-8"), (
            f"pairing drift: {rel} no longer imports httpx"
        )
        assert rel not in sdk_modules, f"pairing drift: own-REST module {rel} now imports an SDK"


def test_sole_http_client_site_uses_httpx2() -> None:
    """Pin the one known http_client= call site: constructed from httpx2, not httpx."""
    site = _REPO_ROOT / "tests/unit/core/llm/test_transport_retry.py"
    text = site.read_text(encoding="utf-8")
    assert _HTTP_CLIENT_ARG_RE.search(text), (
        "expected http_client= site vanished from test_transport_retry.py"
    )
    assert _BARE_HTTPX_CLIENT_CONSTRUCTION_RE.search(text) is None, (
        "http_client= site regressed to bare httpx construction"
    )


# ── Mutation proofs (synthetic violations must turn the guard red) ──


def test_rule1_detects_synthetic_cross_catch(tmp_path: Path) -> None:
    """A fake SDK module catching bare httpx must be flagged."""
    module = tmp_path / "packages/core/fake_sdk_module.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "import openai\nimport httpx\n\n\ndef call() -> None:\n    try:\n        pass\n"
        "    except httpx.HTTPError:\n        pass\n",
        encoding="utf-8",
    )
    assert _find_cross_catch_violations(tmp_path) == [
        "cross-catch: packages/core/fake_sdk_module.py:8"
    ]


def test_rule1_ignores_httpx2_catches(tmp_path: Path) -> None:
    """``except httpx2.`` in an SDK module is the CORRECT pattern — must stay clean."""
    module = tmp_path / "packages/core/fake_sdk_module.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "import openai\nimport httpx2\n\n\ndef call() -> None:\n    try:\n        pass\n"
        "    except httpx2.HTTPError:\n        pass\n",
        encoding="utf-8",
    )
    assert _find_cross_catch_violations(tmp_path) == []


def test_rule1_detects_from_import_cross_catch(tmp_path: Path) -> None:
    """``from httpx import HTTPError`` + bare-name catch must be flagged too."""
    module = tmp_path / "packages/core/fake_sdk_from_import.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "import openai\nfrom httpx import HTTPError\n\n\ndef call() -> None:\n"
        "    try:\n        pass\n    except HTTPError:\n        pass\n",
        encoding="utf-8",
    )
    assert _find_cross_catch_violations(tmp_path) == [
        "cross-catch: packages/core/fake_sdk_from_import.py:8"
    ]


def test_rule1_detects_from_import_tuple_catch(tmp_path: Path) -> None:
    """``except (HTTPError, ValueError):`` after a from-import must be flagged."""
    module = tmp_path / "packages/core/fake_sdk_tuple_catch.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "import openai\nfrom httpx import HTTPError, RequestError\n\n\n"
        "def call() -> None:\n    try:\n        pass\n"
        "    except (HTTPError, ValueError):\n        pass\n",
        encoding="utf-8",
    )
    assert _find_cross_catch_violations(tmp_path) == [
        "cross-catch: packages/core/fake_sdk_tuple_catch.py:8"
    ]


def test_rule1_detects_multiline_from_import_cross_catch(tmp_path: Path) -> None:
    """Multi-line parenthesized ``from httpx import (…)`` + catch must be flagged."""
    module = tmp_path / "packages/core/fake_sdk_multiline_import.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "import openai\nfrom httpx import (\n    HTTPError,\n    RequestError,\n)\n\n\n"
        "def call() -> None:\n    try:\n        pass\n    except HTTPError:\n        pass\n",
        encoding="utf-8",
    )
    assert _find_cross_catch_violations(tmp_path) == [
        "cross-catch: packages/core/fake_sdk_multiline_import.py:11"
    ]


def test_rule1_ignores_httpx2_multiline_from_import_catches(tmp_path: Path) -> None:
    """Multi-line ``from httpx2 import (…)`` + catch is CORRECT — stays clean."""
    module = tmp_path / "packages/core/fake_sdk_httpx2_multiline_import.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "import openai\nfrom httpx2 import (\n    HTTPError,\n    RequestError,\n)\n\n\n"
        "def call() -> None:\n    try:\n        pass\n    except HTTPError:\n        pass\n",
        encoding="utf-8",
    )
    assert _find_cross_catch_violations(tmp_path) == []


def test_rule1_ignores_httpx2_from_import_catches(tmp_path: Path) -> None:
    """``from httpx2 import HTTPError`` + bare-name catch is CORRECT — stays clean."""
    module = tmp_path / "packages/core/fake_sdk_httpx2_from_import.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "import openai\nfrom httpx2 import HTTPError\n\n\ndef call() -> None:\n"
        "    try:\n        pass\n    except HTTPError:\n        pass\n",
        encoding="utf-8",
    )
    assert _find_cross_catch_violations(tmp_path) == []


def test_rule2_detects_synthetic_injection(tmp_path: Path) -> None:
    """``http_client=httpx.AsyncClient()`` must be flagged."""
    module = tmp_path / "packages/core/fake_provider.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "import openai\nimport httpx\n\nclient = openai.OpenAI(http_client=httpx.AsyncClient())\n",
        encoding="utf-8",
    )
    assert _find_http_client_violations(tmp_path) == [
        "http_client-injection: packages/core/fake_provider.py:4"
    ]


def test_rule2_ignores_httpx2_construction(tmp_path: Path) -> None:
    """``http_client=httpx2.AsyncClient()`` is the CORRECT pattern — must stay clean."""
    module = tmp_path / "packages/core/fake_provider.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "import openai\nimport httpx2\n\n"
        "client = openai.OpenAI(http_client=httpx2.AsyncClient())\n",
        encoding="utf-8",
    )
    assert _find_http_client_violations(tmp_path) == []
