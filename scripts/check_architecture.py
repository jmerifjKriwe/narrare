#!/usr/bin/env python3
"""
Narrare Architecture Constraint Checker.

Enforces the rules defined in CONSTRAINTS.md.
Reads configuration from pyproject.toml [tool.narrare.architecture].

Exit code 0: all constraints pass.
Exit code 1: violations found.

See: docs/agents/_shared/CONSTRAINTS.md
"""

from __future__ import annotations

import ast
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent


def load_config() -> dict:  # type: ignore[type-arg]
    config_path = ROOT / "pyproject.toml"
    with config_path.open("rb") as f:
        data = tomllib.load(f)
    return data.get("tool", {}).get("narrare", {}).get("architecture", {})


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class Violation:
    file: Path
    line: int
    rule: str
    detail: str
    approved: bool = False
    approval_reason: str = ""


@dataclass
class CheckResult:
    violations: list[Violation] = field(default_factory=list)
    approved_exceptions: list[Violation] = field(default_factory=list)
    files_checked: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

APPROVAL_MARKER = "# narrare: allow-direct-llm"


def is_approved_exception(source_lines: list[str], lineno: int) -> tuple[bool, str]:
    """Check if the line or its preceding comment has an approval marker."""
    # Check the line itself and the line above
    for check_line in range(max(0, lineno - 2), min(len(source_lines), lineno + 1)):
        line = source_lines[check_line]
        if APPROVAL_MARKER in line:
            reason_start = line.find("reason=")
            reason = ""
            if reason_start != -1:
                reason = line[reason_start + 8 :].strip().strip('"').strip("'")
            return True, reason
    return False, ""


def relative_to_root(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Rule checkers
# ---------------------------------------------------------------------------


def check_llm_imports(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
    allowed_modules: list[str],
    forbidden_imports: list[str],
) -> list[Violation]:
    """RULE-01: No direct LLM imports outside allowed modules."""
    if any(rel_path.startswith(m.rstrip("/")) for m in allowed_modules):
        return []

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            else:
                names = [node.module or ""]

            for name in names:
                root_module = name.split(".")[0]
                if root_module in forbidden_imports:
                    approved, reason = is_approved_exception(source_lines, node.lineno)
                    v = Violation(
                        file=Path(rel_path),
                        line=node.lineno,
                        rule="RULE-01",
                        detail=f"Direct LLM import '{name}' outside gateway",
                        approved=approved,
                        approval_reason=reason,
                    )
                    violations.append(v)
    return violations


def check_llm_urls(
    rel_path: str,
    source: str,
    source_lines: list[str],
    allowed_modules: list[str],
    forbidden_urls: list[str],
) -> list[Violation]:
    """RULE-01: No direct HTTP calls to LLM provider endpoints."""
    if any(rel_path.startswith(m.rstrip("/")) for m in allowed_modules):
        return []

    violations = []
    for i, line in enumerate(source_lines, 1):
        for url in forbidden_urls:
            if url in line:
                approved, reason = is_approved_exception(source_lines, i)
                violations.append(
                    Violation(
                        file=Path(rel_path),
                        line=i,
                        rule="RULE-01",
                        detail=f"Direct HTTP call to LLM endpoint '{url}'",
                        approved=approved,
                        approval_reason=reason,
                    )
                )
    return violations


def check_prompt_building(
    rel_path: str,
    tree: ast.AST,
    source_lines: list[str],
    prompt_allowed: list[str],
) -> list[Violation]:
    """RULE-02: No f-string prompt assembly outside core/prompts/."""
    if any(rel_path.startswith(m.rstrip("/")) for m in prompt_allowed):
        return []

    prompt_var_names = {
        "system_prompt",
        "user_prompt",
        "prompt",
        "system_message",
        "user_message",
    }

    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id.lower() not in prompt_var_names:
                continue
            if isinstance(node.value, ast.JoinedStr):  # f-string
                approved, reason = is_approved_exception(source_lines, node.lineno)
                violations.append(
                    Violation(
                        file=Path(rel_path),
                        line=node.lineno,
                        rule="RULE-02",
                        detail=f"f-string prompt assembly in '{target.id}' outside core/prompts/",
                        approved=approved,
                        approval_reason=reason,
                    )
                )
    return violations


def check_bare_except(
    rel_path: str,
    tree: ast.AST,
) -> list[Violation]:
    """RULE-11: No silent exception swallowing."""
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        # Bare except: (no type specified)
        if node.type is None:
            violations.append(
                Violation(
                    file=Path(rel_path),
                    line=node.lineno,
                    rule="RULE-11",
                    detail="Bare 'except:' clause — must catch specific exception type",
                )
            )
            continue
        # except Exception: pass (body is just Pass)
        if (
            isinstance(node.type, ast.Name)
            and node.type.id == "Exception"
            and len(node.body) == 1
            and isinstance(node.body[0], ast.Pass)
        ):
            violations.append(
                Violation(
                    file=Path(rel_path),
                    line=node.lineno,
                    rule="RULE-11",
                    detail="'except Exception: pass' silently swallows all errors",
                )
            )
    return violations


def check_file_size(
    rel_path: str,
    source_lines: list[str],
    limits: dict[str, int],
) -> list[Violation]:
    """RULE-04: Hard file size limits."""
    line_count = len(source_lines)
    file_name = Path(rel_path).name

    # Determine limit by filename pattern
    limit = limits.get("default", 400)
    if file_name.startswith("router"):
        limit = limits.get("router", 150)
    elif file_name.endswith("_service.py") or file_name == "service.py":
        limit = limits.get("service", 300)
    elif file_name.endswith("_repo.py") or file_name == "repository.py":
        limit = limits.get("repository", 250)
    elif file_name == "contracts.py":
        limit = limits.get("contracts", 200)
    elif file_name == "models.py":
        limit = limits.get("models", 200)
    elif file_name.endswith("_schemas.py") or file_name == "schemas.py":
        limit = limits.get("schemas", 200)
    elif file_name.endswith("_agent.py") or file_name == "agent.py":
        limit = limits.get("agent", 200)
    elif file_name == "gateway.py":
        limit = limits.get("gateway", 300)
    elif file_name == "composer.py":
        limit = limits.get("composer", 250)

    if line_count > limit:
        return [
            Violation(
                file=Path(rel_path),
                line=line_count,
                rule="RULE-04",
                detail=f"File has {line_count} lines (hard limit: {limit}). Split required.",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def scan_file(
    py_file: Path,
    config: dict,  # type: ignore[type-arg]
    result: CheckResult,
) -> None:
    rel_path = relative_to_root(py_file)

    # Skip migrations, tests (except architecture test), venv
    if any(part in rel_path for part in [".venv", "migrations", "node_modules"]):
        return

    try:
        source = py_file.read_text(encoding="utf-8")
    except OSError:
        return

    source_lines = source.splitlines()
    result.files_checked += 1

    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError as e:
        result.violations.append(
            Violation(
                file=py_file,
                line=e.lineno or 0,
                rule="SYNTAX",
                detail=f"Syntax error: {e.msg}",
            )
        )
        return

    allowed_llm = config.get("llm_allowed_modules", [])
    allowed_prompts = config.get("prompt_allowed_modules", [])
    forbidden_imports = config.get("forbidden_llm_imports", [])
    forbidden_urls = config.get("forbidden_llm_urls", [])
    size_limits = config.get("file_size_limits", {})

    all_violations = (
        check_llm_imports(rel_path, tree, source_lines, allowed_llm, forbidden_imports)
        + check_llm_urls(rel_path, source, source_lines, allowed_llm, forbidden_urls)
        + check_prompt_building(rel_path, tree, source_lines, allowed_prompts)
        + check_bare_except(rel_path, tree)
        + check_file_size(rel_path, source_lines, size_limits)
    )

    for v in all_violations:
        if v.approved:
            result.approved_exceptions.append(v)
        else:
            result.violations.append(v)


def main() -> int:
    config = load_config()
    result = CheckResult()

    # Scan all Python files in apps/ and packages/
    scan_roots = [ROOT / "apps", ROOT / "packages", ROOT / "scripts"]
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for py_file in scan_root.rglob("*.py"):
            scan_file(py_file, config, result)

    # Report approved exceptions (visible in CI for review)
    if result.approved_exceptions:
        print("\n⚠️  Approved exceptions (require review in PR):\n")
        for v in result.approved_exceptions:
            print(f"  {v.file}:{v.line}  [{v.rule}]  {v.detail}")
            if v.approval_reason:
                print(f"    → Reason: {v.approval_reason}")

    # Report violations
    if result.violations:
        print("\n❌ Architecture violations found:\n")
        for v in sorted(result.violations, key=lambda x: (str(x.file), x.line)):
            print(f"  {v.file}:{v.line}  [{v.rule}]  {v.detail}")
        print(
            f"\n{len(result.violations)} violation(s) in {result.files_checked} files. Aborting.\n"
        )
        print("See docs/agents/_shared/CONSTRAINTS.md for rules.\n")
        return 1

    print(
        f"✅ Architecture constraints OK "
        f"({result.files_checked} files checked"
        + (
            f", {len(result.approved_exceptions)} approved exception(s)"
            if result.approved_exceptions
            else ""
        )
        + ")"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
