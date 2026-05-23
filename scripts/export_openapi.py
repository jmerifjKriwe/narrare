#!/usr/bin/env python3
"""
Export the Narrare OpenAPI specification to a static JSON file.

Generates the OpenAPI schema from the FastAPI app's route definitions.
This allows external tools (MCP, A2A, third-party) to consume the API
spec without running the server.

Usage:
    uv run python scripts/export_openapi.py              # Write to docs/reference/openapi.json
    uv run python scripts/export_openapi.py --output path # Custom output path
    uv run python scripts/export_openapi.py --check       # CI drift detection (exit 1 on drift)

The script does NOT require Docker, PostgreSQL, or Redis — it only
inspects route definitions and Pydantic models to build the schema.

See: docs/reference/openapi.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Minimal env vars so create_app() succeeds without real infrastructure.
# OpenAPI schema generation is pure-Python; no DB/Redis connections needed.
# ---------------------------------------------------------------------------
os.environ.setdefault("ENVIRONMENT", "test")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = _PROJECT_ROOT / "docs" / "reference" / "openapi.json"


def _generate_schema() -> dict[str, object]:
    """Import the FastAPI app and return its OpenAPI schema dict."""
    from narrare._app.main import app  # type: ignore[import-untyped]

    schema: dict[str, object] = app.openapi()
    return schema


def _serialize(schema: dict[str, object]) -> str:
    """Serialize the schema to formatted JSON."""
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def _write_schema(schema: dict[str, object], output_path: Path) -> None:
    """Write the OpenAPI schema to *output_path*, creating parent dirs."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_serialize(schema), encoding="utf-8")


def _check_drift(schema: dict[str, object], reference_path: Path) -> bool:
    """Return ``True`` if the generated schema differs from *reference_path*.

    Compares parsed JSON dicts so formatting differences are ignored.
    """
    if not reference_path.exists():
        print(
            f"❌ OpenAPI spec not found: {reference_path}",
            file=sys.stderr,
        )
        print("   Run: uv run python scripts/export_openapi.py", file=sys.stderr)
        return True

    try:
        existing = json.loads(reference_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"❌ Invalid JSON in {reference_path}: {exc}", file=sys.stderr)
        return True

    if existing == schema:
        return False

    print("❌ OpenAPI spec drift detected!", file=sys.stderr)
    print(
        f"   The generated schema differs from {reference_path}.",
        file=sys.stderr,
    )
    print(
        "   Regenerate with: uv run python scripts/export_openapi.py",
        file=sys.stderr,
    )
    return True


def main() -> int:
    """CLI entry point. Returns exit code."""
    parser = argparse.ArgumentParser(
        description="Export the Narrare OpenAPI specification to a static JSON file.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output file path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare generated schema with existing file; exit 1 on drift.",
    )
    args = parser.parse_args()

    # --- Generate ---
    try:
        schema = _generate_schema()
    except Exception as exc:
        print(f"❌ Failed to generate OpenAPI schema: {exc}", file=sys.stderr)
        return 1

    paths = len(schema.get("paths", {}))  # type: ignore[arg-type]
    schemas = len(schema.get("components", {}).get("schemas", {}))  # type: ignore[union-attr]

    # --- Check mode (CI) ---
    if args.check:
        has_drift = _check_drift(schema, args.output)
        if has_drift:
            return 1
        print(f"✅ OpenAPI spec up to date ({paths} paths, {schemas} schemas)")
        return 0

    # --- Write mode ---
    _write_schema(schema, args.output)
    print(f"✅ OpenAPI spec written to {args.output} ({paths} paths, {schemas} schemas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
