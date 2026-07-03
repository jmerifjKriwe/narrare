"""AST-based test assertion scanner.

Parses Python test files and detects weak assertion patterns entirely
through AST analysis (stdlib ``ast`` module — no regex). This avoids
false positives from assertions inside comments or string literals.

Patterns detected:
    - ``trivial_truthy`` — bare-name truthy checks
    - ``is_not_none_sole`` — sole assertion is ``is not None``
    - ``status_code_only`` — HTTP status without body validation
    - ``assert_true_literal`` — ``assert True`` / ``assert False``
    - ``response_json_truthy`` — truthy check on ``.json()``
    - ``pytest_raises_no_match`` — exception check without ``match=``
    - ``missing_model_validate`` — file-level schema validation gap
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from .models import (
    RECOMMENDATIONS,
    FileReport,
    Finding,
    WeaknessCategory,
)

# ---------------------------------------------------------------------------
# AST inspection helpers
# ---------------------------------------------------------------------------


def _get_test_functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Collect all test function nodes from the AST.

    Matches top-level ``def test_*`` functions and ``def test_*`` methods
    inside ``class Test*``.
    """
    functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            functions.append(node)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                    item.name.startswith("test_")
                ):
                    functions.append(item)

    return functions


def _get_assert_nodes(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.Assert]:
    """Return all ``ast.Assert`` nodes within a function body."""
    return [n for n in ast.walk(func_node) if isinstance(n, ast.Assert)]


def _extract_line(source: str, lineno: int, max_len: int = 200) -> str:
    """Extract a single source line safely, truncated to *max_len* chars."""
    lines = source.splitlines()
    if 1 <= lineno <= len(lines):
        text = lines[lineno - 1].strip()
        if len(text) > max_len:
            text = text[: max_len - 3] + "..."
        return text
    return f"<line {lineno}>"


# ---------------------------------------------------------------------------
# Pattern matchers (per-assertion)
# ---------------------------------------------------------------------------


def _match_trivial_truthy(node: ast.Assert) -> bool:
    """``assert <name>`` where ``<name>`` is a bare variable (no attribute,
    no comparison, no call)."""
    return isinstance(node.test, ast.Name)


def _match_is_not_none(node: ast.Assert) -> bool:
    """``assert <expr> is not None``."""
    return (
        isinstance(node.test, ast.Compare)
        and len(node.test.ops) == 1
        and isinstance(node.test.ops[0], ast.IsNot)
        and len(node.test.comparators) == 1
        and isinstance(node.test.comparators[0], ast.Constant)
        and node.test.comparators[0].value is None
    )


def _match_status_code(node: ast.Assert) -> bool:
    """``assert response.status_code == <int>`` (or similar attribute)."""
    return (
        isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Attribute)
        and node.test.left.attr == "status_code"
    )


def _match_true_literal(node: ast.Assert) -> bool:
    """``assert True`` or ``assert False``."""
    return isinstance(node.test, ast.Constant) and isinstance(node.test.value, bool)


def _match_response_json_truthy(node: ast.Assert) -> bool:
    """``assert response.json()`` (bare truthy check on ``.json()`` call)."""
    return (
        isinstance(node.test, ast.Call)
        and isinstance(node.test.func, ast.Attribute)
        and node.test.func.attr == "json"
    )


# ---------------------------------------------------------------------------
# Pattern matchers (file-level)
# ---------------------------------------------------------------------------


def _file_has_status_code_check(tree: ast.Module) -> bool:
    """Check if *any* assertion in the file compares ``status_code``."""
    return any(isinstance(node, ast.Assert) and _match_status_code(node) for node in ast.walk(tree))


def _file_has_model_validate(tree: ast.Module) -> bool:
    """Check if ``model_validate`` is called anywhere in the file."""
    return _ast_has_model_validate(tree)


def _func_has_model_validate(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Check if ``model_validate`` is called within a specific function."""
    return _ast_has_model_validate(func_node)


def _ast_has_model_validate(tree: ast.AST) -> bool:
    """Check if ``model_validate`` is called anywhere in the given AST subtree."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "model_validate":
                return True
            if isinstance(func, ast.Name) and func.id == "model_validate":
                return True
    return False


# ---------------------------------------------------------------------------
# Function-level pattern checks
# ---------------------------------------------------------------------------


def _has_pytest_raises_no_match(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Check if the test function calls ``pytest.raises`` without ``match=``.

    Only flags when the ``raises`` function is from the ``pytest`` module.
    """
    for node in ast.walk(func_node):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_raises = False

        if (
            isinstance(func, ast.Attribute)
            and func.attr == "raises"
            and isinstance(func.value, ast.Name)
            and func.value.id == "pytest"
        ):
            is_raises = True

        if not is_raises:
            continue

        # Flag only if no match= keyword argument is present.
        has_match = any(kw.arg == "match" for kw in node.keywords if kw.arg is not None)
        if not has_match:
            return True

    return False


# ---------------------------------------------------------------------------
# Scan entry points
# ---------------------------------------------------------------------------


def scan_file(file_path: Path) -> FileReport | None:
    """Scan a single Python test file for weak assertion patterns.

    Returns ``None`` if the file has no test functions or can't be parsed.
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        if not source.strip():
            return None
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError, UnicodeDecodeError:
        return None

    # File-level analysis.
    file_has_status_code = _file_has_status_code_check(tree)
    file_has_mv = _file_has_model_validate(tree)

    test_funcs = _get_test_functions(tree)
    if not test_funcs:
        return None

    findings: list[Finding] = []
    total_assertions = 0

    for func in test_funcs:
        assertions = _get_assert_nodes(func)
        total_assertions += len(assertions)

        func_has_mv = _func_has_model_validate(func)

        for assert_node in assertions:
            line = assert_node.lineno
            snippet = _extract_line(source, line)

            # --- per-assertion pattern checks ---

            if _match_true_literal(assert_node):
                findings.append(
                    Finding(
                        category=WeaknessCategory.ASSERT_TRUE_LITERAL,
                        file_path=file_path,
                        line=line,
                        code_snippet=snippet,
                        weight=1.0,
                        recommendation=RECOMMENDATIONS[WeaknessCategory.ASSERT_TRUE_LITERAL],
                    )
                )
            elif _match_trivial_truthy(assert_node):
                findings.append(
                    Finding(
                        category=WeaknessCategory.TRIVIAL_TRUTHY,
                        file_path=file_path,
                        line=line,
                        code_snippet=snippet,
                        weight=0.6,
                        recommendation=RECOMMENDATIONS[WeaknessCategory.TRIVIAL_TRUTHY],
                    )
                )
            elif _match_response_json_truthy(assert_node):
                findings.append(
                    Finding(
                        category=WeaknessCategory.RESPONSE_JSON_TRUTHY,
                        file_path=file_path,
                        line=line,
                        code_snippet=snippet,
                        weight=0.5,
                        recommendation=RECOMMENDATIONS[WeaknessCategory.RESPONSE_JSON_TRUTHY],
                    )
                )
            elif _match_status_code(assert_node) and not func_has_mv:
                findings.append(
                    Finding(
                        category=WeaknessCategory.STATUS_CODE_ONLY,
                        file_path=file_path,
                        line=line,
                        code_snippet=snippet,
                        weight=0.3,
                        recommendation=RECOMMENDATIONS[WeaknessCategory.STATUS_CODE_ONLY],
                    )
                )

        # --- single-assertion checks (function-level) ---

        if len(assertions) == 1 and _match_is_not_none(assertions[0]):
            findings.append(
                Finding(
                    category=WeaknessCategory.IS_NOT_NONE_SOLE,
                    file_path=file_path,
                    line=assertions[0].lineno,
                    code_snippet=_extract_line(source, assertions[0].lineno),
                    weight=0.4,
                    recommendation=RECOMMENDATIONS[WeaknessCategory.IS_NOT_NONE_SOLE],
                )
            )

        # --- pytest.raises without match= ---

        if _has_pytest_raises_no_match(func):
            # Walk to find the specific pytest.raises call node for line info.
            for node in ast.walk(func):
                if not isinstance(node, ast.Call):
                    continue
                func_ref = node.func
                is_pytest_raises = (
                    isinstance(func_ref, ast.Attribute)
                    and func_ref.attr == "raises"
                    and isinstance(func_ref.value, ast.Name)
                    and func_ref.value.id == "pytest"
                )
                if is_pytest_raises:
                    has_match = any(kw.arg == "match" for kw in node.keywords if kw.arg is not None)
                    if not has_match:
                        findings.append(
                            Finding(
                                category=WeaknessCategory.PYTEST_RAISES_NO_MATCH,
                                file_path=file_path,
                                line=node.lineno,
                                code_snippet=_extract_line(source, node.lineno),
                                weight=0.3,
                                recommendation=RECOMMENDATIONS[
                                    WeaknessCategory.PYTEST_RAISES_NO_MATCH
                                ],
                            )
                        )

    # --- file-level checks ---

    if file_has_status_code and not file_has_mv:
        findings.append(
            Finding(
                category=WeaknessCategory.MISSING_MODEL_VALIDATE,
                file_path=file_path,
                line=1,
                code_snippet="",
                weight=0.2,
                recommendation=RECOMMENDATIONS[WeaknessCategory.MISSING_MODEL_VALIDATE],
            )
        )

    # Calculate aggregate score.
    score = _compute_score(findings, total_assertions)

    return FileReport(
        file_path=file_path,
        total_assertions=total_assertions,
        findings=findings,
        score=score,
    )


def _compute_score(findings: list[Finding], total_assertions: int) -> float:
    """Compute the aggregate weakness score for a file.

    Formula: ``min(1.0, sum(weights) / max(1, total_assertions))``
    """
    if total_assertions == 0:
        return 0.0
    total_weight = sum(f.weight for f in findings)
    return min(1.0, total_weight / total_assertions)


def scan_directory(
    base_path: Path,
    threshold: float = 0.0,
) -> list[FileReport]:
    """Recursively scan all ``.py`` files in *base_path* for weak assertions.

    Only returns files whose ``score >= threshold``.
    """
    reports: list[FileReport] = []
    for py_file in sorted(base_path.rglob("*.py")):
        if py_file.name in {"__init__.py", "conftest.py"}:
            continue
        report = scan_file(py_file)
        if report is not None and report.score >= threshold:
            reports.append(report)
    return reports
