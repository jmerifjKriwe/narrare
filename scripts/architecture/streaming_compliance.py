"""Shared types and matchers for RULE-20 streaming compliance checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


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
