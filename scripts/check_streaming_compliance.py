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
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "apps" / "api" / "narrare"
WEB_DIR = REPO_ROOT / "packages" / "web"

# SSE endpoint signatures: (router_file_pattern, url_substring, http_method)
# url_substring is the route path after the APIRouter prefix.
KNOWN_SSE_ENDPOINTS: list[tuple[str, str, str]] = [
    # (router filename glob, URL fragment, HTTP method)
    ("**/writing/router.py", "/writing/generation/", "GET"),
    ("**/writing/router_extend.py", "/writing/chapters/", "POST"),
    ("**/writing/router_rewrite.py", "/writing/chapters/", "POST"),
    ("**/writing/router_coauthor.py", "/writing/chapters/", "POST"),
    ("**/writing/router_suggest.py", "/writing/chapters/", "POST"),
    ("**/kb/router_sessions_sse.py", "/kb/sessions/", "GET"),
    ("**/planning/router_timeline_analysis.py", "/timeline/", "POST"),
    ("**/chat/router.py", "/chat", "POST"),
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SSEEndpoint:
    """A backend SSE endpoint discovered from router files."""

    file: Path
    route: str  # full route path (e.g. /api/v1/writing/chapters/{id}/extend)
    method: str
    prefix: str  # APIRouter prefix
    name: str  # human-readable label (derived from file path)


@dataclass
class FrontendConsumer:
    """A frontend API call that consumes a backend endpoint."""

    file: Path
    line: int
    uses_sse: bool  # True if connectSSE is used
    url_fragment: str  # URL pattern used in the call


@dataclass
class ComplianceResult:
    """Overall compliance check result."""

    sse_endpoints: list[SSEEndpoint] = field(default_factory=list[SSEEndpoint])
    consumers: list[FrontendConsumer] = field(default_factory=list[FrontendConsumer])
    passes: list[str] = field(default_factory=list[str])
    violations: list[str] = field(default_factory=list[str])


# ---------------------------------------------------------------------------
# Backend SSE endpoint discovery
# ---------------------------------------------------------------------------


def _find_router_files() -> list[Path]:
    """Find all Python router files in the API directory."""
    return list(API_DIR.rglob("router*.py")) + list(API_DIR.rglob("router_*.py"))


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
    """Extract StreamingResponse endpoint routes from a router file."""
    endpoints: list[SSEEndpoint] = []
    current_route: str | None = None
    current_method: str | None = None

    for line in source.split("\n"):
        m = re.match(r'\s*@router\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']*)["\']', line)
        if m:
            current_method = m.group(1).upper()
            current_route = m.group(2)
            continue
        if current_route is not None and "StreamingResponse" in line:
            parts = filepath.relative_to(API_DIR).parts
            name = f"{parts[0]}/{filepath.stem}" if len(parts) > 1 else filepath.stem
            endpoints.append(
                SSEEndpoint(
                    file=filepath,
                    route=f"/api/v1{prefix}{current_route}",
                    method=current_method or "GET",
                    prefix=prefix,
                    name=name,
                )
            )
            current_route = None
            current_method = None

    return endpoints


def discover_sse_endpoints() -> list[SSEEndpoint]:
    """Discover all SSE endpoints from backend router files."""
    endpoints: list[SSEEndpoint] = []
    for router_file in _find_router_files():
        try:
            source = router_file.read_text(encoding="utf-8")
        except OSError:
            continue
        if "StreamingResponse" not in source:
            continue
        prefix = _extract_router_prefix(source)
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


def _url_patterns_match(endpoint_url: str, consumer_url: str) -> bool:
    """Check if a consumer URL matches an SSE endpoint URL by structural comparison."""
    # Normalize path parameters: {anything} → {}
    norm_endpoint = re.sub(r"\{[^}]+\}", "{}", endpoint_url)
    norm_consumer = re.sub(r"\{[^}]+\}|\$\{[^}]+\}", "{}", consumer_url)
    norm_consumer = re.sub(r"\$\w+", "{}", norm_consumer)

    ep_parts = [p for p in norm_endpoint.split("/") if p]
    co_parts = [p for p in norm_consumer.split("/") if p]

    if len(ep_parts) < 3 or len(co_parts) < 3:
        return False

    # Compare from the end: the last N segments should match
    # where N = min(len(co_parts), number of meaningful segments)
    ep_len = len(ep_parts)
    co_len = len(co_parts)

    # Walk backwards and match segments
    matched_from_end = 0
    for i in range(1, min(ep_len, co_len) + 1):
        ep_seg = ep_parts[ep_len - i]
        co_seg = co_parts[co_len - i]
        if ep_seg == co_seg:
            matched_from_end += 1
        elif ep_seg == "{}" or co_seg == "{}":
            matched_from_end += 1  # parameter matches anything
        else:
            break

    # Need at least 2 matching trailing segments for a meaningful match
    # (e.g. "generation/stream" or "chapters/extend")
    if matched_from_end < 2:
        return False

    # Also verify at least one leading segment matches (same API domain)
    if ep_parts[0] != co_parts[0]:
        return False

    return not abs(ep_len - co_len) > 1


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
            # No consumer found at all — not a violation per se (might be unused)
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
                f"  → {consumer.file.relative_to(REPO_ROOT)}:{consumer.line}\n"
                f"  → Backend SSE: {endpoint.file.relative_to(REPO_ROOT)}"
            )

    return result


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
                    "file": str(e.file.relative_to(REPO_ROOT)),
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
    args = parser.parse_args()

    result = check_compliance()

    if args.json:
        print(format_json(result))
    else:
        print(format_report(result))

    return 1 if result.violations else 0


if __name__ == "__main__":
    sys.exit(main())
