"""HTTPx cross-catch regression guard tests for the dual-httpx regime.

Governance sweep in the ``doc_drift`` style: clean-baseline ratchets against
the real tree (including a parse ratchet so Rule 1's scope can never shrink
silently) plus tmp-injection mutation proofs.

The detection engine lives in the sibling
``tests/unit/scripts/_httpx_cross_catch_support.py`` — same test tree, not
production code (``tests/`` is outside pyright's CI ``include``, see
``pyproject.toml``); the split keeps both files under the RULE-04 size limit.
Rule 1 (AST-based cross-catch) and Rule 2 (regex same-file ``http_client=``
injection heuristic) semantics are documented there.
"""

from __future__ import annotations

from pathlib import Path

from tests.unit.scripts import _httpx_cross_catch_support
from tests.unit.scripts._httpx_cross_catch_support import (
    _BARE_HTTPX_CLIENT_CONSTRUCTION_RE,
    _HTTP_CLIENT_ARG_RE,
    _KNOWN_OWN_REST_MODULES,
    _REPO_ROOT,
    _RULE1_ROOTS,
    _find_cross_catch_violations,
    _find_http_client_violations,
    _find_sdk_modules,
    _parse_module,
    _python_files,
)

# Rule 2 self-exclusion (governance-sweep convention). Load-bearing half: this
# test file — its mutation fixtures contain ``http_client=httpx.…`` literals by
# design. Defensive half: the engine module — its prose does not match the
# offender regex today (verified), excluded belt-and-suspenders so neither
# guard file can ever flag its own sweep.
_GUARD_FILES = (Path(__file__), Path(_httpx_cross_catch_support.__file__))


# ── Clean baseline against the real repo tree ────────────────────


def test_rule1_clean_baseline() -> None:
    """No SDK-importing module catches bare-httpx exceptions (current tree).

    Parse ratchet: every scanned ``.py`` file must parse with ``ast`` — a file
    that fails ``ast.parse`` would silently shrink Rule 1's scope (the exact
    silent-miss class this guard exists to kill), so unparseable files fail
    the baseline instead of being skipped silently.
    """
    unparseable = [
        str(path.relative_to(_REPO_ROOT))
        for path in _python_files(_REPO_ROOT, _RULE1_ROOTS)
        if _parse_module(path) is None
    ]
    assert unparseable == [], f"files silently skipped by the Rule 1 AST parse: {unparseable}"
    violations = _find_cross_catch_violations(_REPO_ROOT)
    assert violations == [], f"bare httpx cross-catch in SDK modules: {violations}"


def test_rule2_clean_baseline() -> None:
    """No http_client= site is fed a bare-httpx-constructed client (current tree)."""
    violations = _find_http_client_violations(_REPO_ROOT, exclude=_GUARD_FILES)
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


def test_rule1_detects_module_alias_cross_catch(tmp_path: Path) -> None:
    """``import httpx as hx`` + ``except hx.HTTPError:`` must be flagged (AST binding)."""
    module = tmp_path / "packages/core/fake_sdk_alias_module.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "import openai\nimport httpx as hx\n\n\ndef call() -> None:\n    try:\n        pass\n"
        "    except hx.HTTPError:\n        pass\n",
        encoding="utf-8",
    )
    assert _find_cross_catch_violations(tmp_path) == [
        "cross-catch: packages/core/fake_sdk_alias_module.py:8"
    ]


def test_rule1_detects_module_alias_tuple_catch(tmp_path: Path) -> None:
    """``except (hx.HTTPError, ValueError):`` after a module-alias import must be flagged."""
    module = tmp_path / "packages/core/fake_sdk_alias_tuple.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "import openai\nimport httpx as hx\n\n\ndef call() -> None:\n"
        "    try:\n        pass\n    except (hx.HTTPError, ValueError):\n        pass\n",
        encoding="utf-8",
    )
    assert _find_cross_catch_violations(tmp_path) == [
        "cross-catch: packages/core/fake_sdk_alias_tuple.py:8"
    ]


def test_rule1_detects_module_alias_except_star_catch(tmp_path: Path) -> None:
    """``except* hx.HTTPError:`` in an SDK module must be flagged (ast.TryStar)."""
    module = tmp_path / "packages/core/fake_sdk_except_star.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "import openai\nimport httpx as hx\n\n\ndef call() -> None:\n"
        "    try:\n        pass\n    except* hx.HTTPError:\n        pass\n",
        encoding="utf-8",
    )
    assert _find_cross_catch_violations(tmp_path) == [
        "cross-catch: packages/core/fake_sdk_except_star.py:8"
    ]


def test_rule1_ignores_docstring_only_sdk_mention(tmp_path: Path) -> None:
    """A docstring mention of ``import openai`` is not a real SDK import.

    Own-REST style module (real ``from httpx import`` + catch is legal there):
    the SDK-module classifier must consider real imports only, not prose.
    """
    module = tmp_path / "packages/core/fake_docstring_mention.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        '"""Docs say: import openai somewhere else."""\n'
        "from httpx import HTTPError\n\n\n"
        "def call() -> None:\n    try:\n        pass\n    except HTTPError:\n        pass\n",
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
