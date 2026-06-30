#!/usr/bin/env python3
"""RULE-20 Streaming Compliance Check.

Verifies every backend SSE endpoint has a frontend consumer using
``connectSSE()``. Reports violations where REST calls are used instead.

Usage: python scripts/check_streaming_compliance.py [--json]
Exit: 0 = compliant, 1 = violations found
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.architecture.baselines import (  # noqa: E402
    DEFAULT_BASELINE_PATH,
    compare_section,
    format_comparison,
    stable_fingerprint,
)
from scripts.architecture.streaming_compliance import (  # noqa: E402
    ComplianceResult,
    FrontendConsumer,
    SSEEndpoint,
    extract_route_decorators,
    url_patterns_match,
)
from scripts.architecture.streaming_compliance import (  # noqa: E402
    build_effective_router_prefixes as _build_effective_router_prefixes,
)

API_DIR = REPO_ROOT / "apps" / "api" / "narrare"
WEB_DIR = REPO_ROOT / "packages" / "web"
STREAMING_BASELINE_SECTION = "streaming_compliance_gaps"
_url_patterns_match = url_patterns_match


def _display_path(path: Path, base: Path = REPO_ROOT) -> str:
    """Return a stable display path, tolerating synthetic test paths."""
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


# ---------------------------------------------------------------------------
# Backend SSE endpoint discovery
# ---------------------------------------------------------------------------


def _find_router_files() -> list[Path]:
    """Find all Python router files in the API directory."""
    return sorted(set(API_DIR.rglob("router*.py")) | set(API_DIR.rglob("router_*.py")))


def _extract_router_prefix(source: str) -> str:
    """Extract APIRouter(prefix=...) from router source code."""
    # Try AST first
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "APIRouter":
                    for kw in node.keywords:
                        if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                            return str(kw.value.value)
    except SyntaxError:
        pass
    # Fallback to regex
    m = re.search(r'APIRouter\([^)]*prefix\s*=\s*["\']([^"\']+)["\']', source)
    return m.group(1) if m else ""


def _extract_sse_routes(source: str, prefix: str, filepath: Path) -> list[SSEEndpoint]:
    """Extract StreamingResponse endpoint routes using AST-based decorator extraction.

    Delegates to ``extract_route_decorators()`` for the AST parsing, then
    filters to functions whose body contains ``StreamingResponse``.
    """
    endpoints: list[SSEEndpoint] = []
    lines = source.split("\n")

    parts = Path(_display_path(filepath, API_DIR)).parts
    name = f"{parts[0]}/{filepath.stem}" if len(parts) > 1 else filepath.stem

    for rd in extract_route_decorators(source):
        # Source range from first decorator to end of function body
        body = "\n".join(lines[rd.decorator_lineno - 1 : rd.func_end_lineno])
        if "StreamingResponse" not in body:
            continue

        endpoints.append(
            SSEEndpoint(
                file=filepath,
                route=f"/api/v1{prefix}{rd.path}",
                method=rd.http_method,
                prefix=prefix,
                name=name,
            )
        )

    return endpoints


def discover_sse_endpoints() -> list[SSEEndpoint]:
    """Discover all SSE endpoints from backend router files."""
    endpoints: list[SSEEndpoint] = []
    router_files = _find_router_files()
    effective_prefixes = _build_effective_router_prefixes(router_files, _extract_router_prefix)
    for router_file in router_files:
        try:
            source = router_file.read_text(encoding="utf-8")
        except OSError:
            continue
        if "StreamingResponse" not in source:
            continue
        for prefix in effective_prefixes.get(router_file, [_extract_router_prefix(source)]):
            endpoints.extend(_extract_sse_routes(source, prefix, router_file))
    return endpoints


# ---------------------------------------------------------------------------
# Frontend consumer discovery
# ---------------------------------------------------------------------------


def _find_frontend_api_files() -> list[Path]:
    """Find TypeScript API client files in the web package."""
    files: list[Path] = []
    for pattern in ("lib/api/**/*.ts", "lib/hooks/**/*.ts"):
        files.extend(WEB_DIR.rglob(pattern))
    return [f for f in files if f.suffix == ".ts" and ".test." not in f.name]


def _check_file_uses_sse(source: str) -> bool:
    """Check if a file imports or uses connectSSE."""
    return "connectSSE" in source


def _extract_url_patterns(source: str, filepath: Path) -> list[FrontendConsumer]:
    """Extract API URL patterns from a frontend TypeScript file."""
    consumers: list[FrontendConsumer] = []
    uses_sse = _check_file_uses_sse(source)
    kw_filter = ("chapters", "writing", "sessions", "timeline", "chat", "extract")

    for i, line in enumerate(source.split("\n")):
        for m in re.finditer(r'[`"\'](/api/v1/[^`"\']+)[`"\']', line):
            consumers.append(
                FrontendConsumer(
                    file=filepath,
                    line=i + 1,
                    uses_sse=uses_sse,
                    url_fragment=m.group(1),
                )
            )
        for m in re.finditer(r'[`"\'](/[a-z]+/[a-z_]+/[^`"\']*)[`"\']', line):
            url = m.group(1)
            if any(kw in url for kw in kw_filter):
                consumers.append(
                    FrontendConsumer(
                        file=filepath,
                        line=i + 1,
                        uses_sse=uses_sse,
                        url_fragment=url,
                    )
                )

    # connectSSE url-parameter detection.
    # connectSSE() always prepends /api/v1 to the url argument internally
    # (see streaming.ts: fetch(`/api/v1${url}`)), so the source file only
    # contains the short form (e.g. "/chat" or `/writing/chapters/${id}/...`).
    # Extract these url: properties and construct the full route.
    # Skip lines already covered by the generic patterns above to avoid
    # duplicate PASS entries in the report.
    if uses_sse:
        covered_lines = {c.line for c in consumers}
        for i, line in enumerate(source.split("\n")):
            lineno = i + 1
            if lineno in covered_lines:
                continue
            m = re.search(r'\burl:\s*[`"\'](/[^`"\']+)[`"\']', line)
            if m:
                consumers.append(
                    FrontendConsumer(
                        file=filepath,
                        line=lineno,
                        uses_sse=True,
                        url_fragment=f"/api/v1{m.group(1)}",
                    )
                )

    return consumers


def discover_frontend_consumers() -> list[FrontendConsumer]:
    """Discover all frontend API consumers."""
    consumers: list[FrontendConsumer] = []
    for api_file in _find_frontend_api_files():
        try:
            source = api_file.read_text(encoding="utf-8")
        except OSError:
            continue
        consumers.extend(_extract_url_patterns(source, api_file))
    return consumers


# ---------------------------------------------------------------------------
# Compliance checking
# ---------------------------------------------------------------------------


def check_compliance() -> ComplianceResult:
    """Run the full compliance check."""
    result = ComplianceResult()

    # Discover
    result.sse_endpoints = discover_sse_endpoints()
    result.consumers = discover_frontend_consumers()

    # For each SSE endpoint, find matching frontend consumers
    for endpoint in result.sse_endpoints:
        matching_consumers = [
            c for c in result.consumers if _url_patterns_match(endpoint.route, c.url_fragment)
        ]

        if not matching_consumers:
            result.violations.append(
                f"{endpoint.name} has no frontend SSE consumer found\n"
                f"  → Backend SSE: {_display_path(endpoint.file)}"
            )
            continue

        sse_consumers = [c for c in matching_consumers if c.uses_sse]
        rest_consumers = [c for c in matching_consumers if not c.uses_sse]

        # Report SSE consumers as passes
        for consumer in sse_consumers:
            label = _derive_consumer_label(consumer)
            result.passes.append(f"{endpoint.name} uses connectSSE via {label}")

        # Report REST consumers as violations
        for consumer in rest_consumers:
            label = _derive_consumer_label(consumer)
            result.violations.append(
                f"{endpoint.name} uses apiClient call instead of connectSSE\n"
                f"  → {_display_path(consumer.file)}:{consumer.line}\n"
                f"  → Backend SSE: {_display_path(endpoint.file)}"
            )

    return result


def violation_fingerprints(result: ComplianceResult) -> set[str]:
    """Return stable fingerprints for streaming coverage gaps."""
    return {
        stable_fingerprint(*[line.strip() for line in violation.splitlines()])
        for violation in result.violations
    }


def _derive_consumer_label(consumer: FrontendConsumer) -> str:
    """Derive a short label from the consumer file path."""
    try:
        rel = consumer.file.relative_to(REPO_ROOT / "packages" / "web")
        parts = rel.parts
        if len(parts) >= 3:
            return f"{parts[-2]}/{parts[-1]}"
        return rel.name
    except ValueError:
        return consumer.file.name


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_report(result: ComplianceResult) -> str:
    """Format the compliance result as a human-readable report."""
    lines: list[str] = []
    lines.append("RULE-20 Streaming Compliance Check")
    lines.append("=" * 40)
    lines.append(f"SSE endpoints found: {len(result.sse_endpoints)}")
    lines.append(f"Frontend consumers checked: {len(result.consumers)}")
    lines.append("")

    for msg in result.passes:
        lines.append(f"✅ PASS: {msg}")

    for msg in result.violations:
        lines.append(f"❌ VIOLATION: {msg}")

    if not result.violations:
        lines.append("✅ All SSE-capable endpoints use streaming on the frontend.")

    return "\n".join(lines)


def format_json(result: ComplianceResult) -> str:
    """Format the compliance result as JSON."""
    return json.dumps(
        {
            "sse_endpoints": [
                {
                    "file": _display_path(e.file),
                    "route": e.route,
                    "method": e.method,
                    "name": e.name,
                }
                for e in result.sse_endpoints
            ],
            "violations": result.violations,
            "passes": result.passes,
            "compliant": len(result.violations) == 0,
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="RULE-20 Streaming Compliance Check")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE_PATH)
    parser.add_argument("--no-baseline", action="store_true")
    args = parser.parse_args()

    result = check_compliance()

    if args.json:
        print(format_json(result))
    else:
        print(format_report(result))

    if args.no_baseline:
        return 1 if result.violations else 0

    comparison = compare_section(
        violation_fingerprints(result),
        STREAMING_BASELINE_SECTION,
        args.baseline,
    )
    print(format_comparison(comparison, "Streaming compliance ratchet"))
    if comparison.ok:
        print("RESULT: Streaming compliance gaps did not grow")
        return 0
    print("RESULT: New streaming compliance gap(s) require frontend SSE coverage")
    return 1


if __name__ == "__main__":
    sys.exit(main())
