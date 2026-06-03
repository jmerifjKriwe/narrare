"""Shared types and matchers for RULE-20 streaming compliance checks."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
API_DIR = REPO_ROOT / "apps" / "api" / "narrare"


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


def url_patterns_match(endpoint_url: str, consumer_url: str) -> bool:
    """Check whether a consumer URL structurally matches an SSE endpoint URL."""
    endpoint_url = normalize_comparable_url(endpoint_url)
    consumer_url = normalize_comparable_url(consumer_url)

    # Normalize path parameters: {anything} → {}
    norm_endpoint = re.sub(r"\{[^}]+\}", "{}", endpoint_url)
    norm_consumer = re.sub(r"\{[^}]+\}|\$\{[^}]+\}", "{}", consumer_url)
    norm_consumer = re.sub(r"\$\w+", "{}", norm_consumer)

    ep_parts = [p for p in norm_endpoint.split("/") if p]
    co_parts = [p for p in norm_consumer.split("/") if p]

    if len(ep_parts) != len(co_parts):
        return False

    return all(
        url_segments_match(endpoint, consumer)
        for endpoint, consumer in zip(ep_parts, co_parts, strict=True)
    )


def url_segments_match(endpoint_segment: str, consumer_segment: str) -> bool:
    """Return whether two aligned URL path segments describe the same endpoint."""
    if endpoint_segment == consumer_segment:
        return True
    return endpoint_segment == "{}" and bool(consumer_segment)


def normalize_comparable_url(url: str) -> str:
    """Normalize frontend/backend URL variants before structural comparison."""
    path = url.split("?", 1)[0].split("#", 1)[0]
    if path.startswith("/api/v1/"):
        return path.removeprefix("/api/v1")
    return path


def join_url_paths(*parts: str) -> str:
    """Join URL path fragments while preserving a single leading slash."""
    cleaned = [part.strip("/") for part in parts if part and part != "/"]
    if not cleaned:
        return ""
    return f"/{'/'.join(cleaned)}"


def module_to_router_file(module: str, api_dir: Path = API_DIR) -> Path | None:
    """Resolve a ``narrare.*`` module import to a router file path."""
    if not module.startswith("narrare."):
        return None
    relative_module = module.removeprefix("narrare.").replace(".", "/")
    return api_dir / f"{relative_module}.py"


def extract_router_import_aliases(source: str, api_dir: Path = API_DIR) -> dict[str, Path]:
    """Map imported router aliases to their source files."""
    aliases: dict[str, Path] = {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return aliases

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        module_file = module_to_router_file(node.module, api_dir)
        if module_file is None:
            continue
        for alias in node.names:
            if alias.name != "router":
                continue
            aliases[alias.asname or alias.name] = module_file
    return aliases


def extract_included_router_aliases(source: str) -> list[tuple[str, str]]:
    """Extract ``include_router(alias, prefix=...)`` relationships."""
    includes: list[tuple[str, str]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return includes

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "include_router":
            continue
        if not node.args or not isinstance(node.args[0], ast.Name):
            continue
        include_prefix = ""
        for kw in node.keywords:
            if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                include_prefix = str(kw.value.value)
        includes.append((node.args[0].id, include_prefix))
    return includes


def infer_api_dir(router_files: list[Path]) -> Path:
    """Infer the API package root for real or synthetic router files."""
    for router_file in router_files:
        for parent in router_file.parents:
            if parent.name == "narrare" and parent.parent.name == "api":
                return parent
    return API_DIR


def build_effective_router_prefixes(
    router_files: list[Path],
    extract_router_prefix: Callable[[str], str],
) -> dict[Path, list[str]]:
    """Build route prefixes including nested ``include_router`` parents.

    FastAPI composes prefixes when a router includes another router. The
    streaming check must model that composition so a child router such as
    ``planning/router_timeline_analysis.py`` is compared against its real
    product URL (``/planning/timeline/...``), not only its local prefix
    (``/timeline/...``).
    """
    api_dir = infer_api_dir(router_files)
    sources: dict[Path, str] = {}
    own_prefixes: dict[Path, str] = {}
    child_to_parents: dict[Path, list[tuple[Path, str]]] = {}

    for router_file in router_files:
        try:
            source = router_file.read_text(encoding="utf-8")
        except OSError:
            continue
        sources[router_file] = source
        own_prefixes[router_file] = extract_router_prefix(source)

    for parent_file, source in sources.items():
        import_aliases = extract_router_import_aliases(source, api_dir)
        for alias, include_prefix in extract_included_router_aliases(source):
            child_file = import_aliases.get(alias)
            if child_file is None or child_file not in own_prefixes:
                continue
            child_to_parents.setdefault(child_file, []).append((parent_file, include_prefix))

    cache: dict[Path, list[str]] = {}

    def effective_prefixes(router_file: Path, seen: set[Path] | None = None) -> list[str]:
        if router_file in cache:
            return cache[router_file]
        seen = seen or set()
        if router_file in seen:
            cache[router_file] = [own_prefixes.get(router_file, "")]
            return cache[router_file]
        seen.add(router_file)

        parents = child_to_parents.get(router_file, [])
        own_prefix = own_prefixes.get(router_file, "")
        if not parents:
            prefixes = [own_prefix]
        else:
            prefixes: list[str] = []
            for parent_file, include_prefix in parents:
                for parent_prefix in effective_prefixes(parent_file, seen.copy()):
                    prefixes.append(join_url_paths(parent_prefix, include_prefix, own_prefix))
        cache[router_file] = sorted(set(prefixes))
        return cache[router_file]

    return {router_file: effective_prefixes(router_file) for router_file in own_prefixes}
