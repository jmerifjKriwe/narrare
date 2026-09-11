"""Guard tests: the dual-output agent pattern must not silently return.

After the dual-output unification (Tasks 1-5), agents use a single strict
output model via ``output_type=StrictModel``. These guards ban:

1. The attribute form ``output_type=[`` (list-of-models dual output).
2. The dict-key form ``"output_type": [`` (bypass-kwargs dual output).
3. The deleted twin-processing pattern (``_process_`` methods) in agents/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PRODUCTION_ROOT = Path(__file__).resolve().parents[4] / "packages" / "core" / "narrare_core"
AGENTS_ROOT = PRODUCTION_ROOT / "agents"

ATTRIBUTE_PATTERN = "output_type=["
DICT_KEY_PATTERN = '"output_type": ['
TWIN_METHOD_PATTERN = "_process_"


def _production_python_files(root: Path) -> list[Path]:
    """Return all production .py files under root, skipping caches."""
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _find_violations(root: Path, pattern: str) -> list[str]:
    """Find files under root containing pattern; report file + line."""
    violations: list[str] = []
    for path in _production_python_files(root):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if pattern in line:
                violations.append(f"{path}:{lineno}: {line.strip()}")
    return violations


def test_production_root_exists() -> None:
    assert PRODUCTION_ROOT.is_dir(), f"missing production root: {PRODUCTION_ROOT}"
    assert AGENTS_ROOT.is_dir(), f"missing agents root: {AGENTS_ROOT}"


def test_no_dual_output_attribute_form_in_production() -> None:
    violations = _find_violations(PRODUCTION_ROOT, ATTRIBUTE_PATTERN)
    assert not violations, (
        "dual-output attribute form 'output_type=[' found in production:\n" + "\n".join(violations)
    )


def test_no_dual_output_dict_key_form_in_production() -> None:
    violations = _find_violations(PRODUCTION_ROOT, DICT_KEY_PATTERN)
    assert not violations, (
        "dual-output dict-key form '\"output_type\": [' found in production:\n"
        + "\n".join(violations)
    )


def test_no_twin_process_methods_in_agents() -> None:
    violations = [
        violation
        for violation in _find_violations(AGENTS_ROOT, TWIN_METHOD_PATTERN)
        if not violation.split(":", 1)[0].endswith("__init__.py")
    ]
    assert not violations, "deleted twin pattern '_process_' reappeared in agents/:\n" + "\n".join(
        sorted(set(violations))
    )


@pytest.mark.parametrize(
    ("pattern", "description"),
    [
        (ATTRIBUTE_PATTERN, "attribute form"),
        (DICT_KEY_PATTERN, "dict-key form"),
    ],
)
def test_patterns_are_distinct_and_nonempty(pattern: str, description: str) -> None:
    """Sanity: guard patterns must never degenerate into trivial matches."""
    assert pattern, f"{description} guard pattern must not be empty"
    assert "[" in pattern, f"{description} guard pattern must anchor on list literal"
