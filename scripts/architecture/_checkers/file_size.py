"""RULE-04 · File size limits."""

from __future__ import annotations

from pathlib import Path

from scripts.architecture.types import Violation


def check_file_size(
    rel_path: str,
    source_lines: list[str],
    limits: dict[str, int],
) -> list[Violation]:
    """Hard file size limits by file type."""
    line_count = len(source_lines)
    file_name = Path(rel_path).name

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
