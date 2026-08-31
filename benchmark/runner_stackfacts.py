"""Stack identity facts for the run manifest (plan Tasks 14/15 wiring).

Assembles the artifact writer's ``StackFacts`` record from the run's two
live seams: the compose stack (compose file SHA-256 + per-service image
digests — the stack manager owns those providers per the Task 14
contract) and the API client (the version payload).

API version: NO dedicated ``/version`` endpoint exists (api-surface.md
§5, OPEN-1) — the payload is read from ``GET /openapi.json`` →
``info.version``. Shape drift fails loudly (a manifest claiming an
unknown-version stack would be a fabricated fact).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Protocol, cast

from benchmark.artifacts_records import StackFacts

if TYPE_CHECKING:
    from collections.abc import Mapping

    import httpx

__all__ = ["api_version_payload", "stack_facts"]

_OPENAPI_PATH: Final[str] = "/openapi.json"


class FactsStack(Protocol):
    """The stack seam's facts half (``StackManager.facts``)."""

    def facts(self) -> tuple[str, tuple[tuple[str, str], ...]]: ...


class FactsClient(Protocol):
    """The client seam's request half (``BenchmarkClient.request``)."""

    def request(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response: ...


def stack_facts(stack: FactsStack, client: FactsClient) -> StackFacts:
    """Assemble ``StackFacts`` from the stack manager + the API client."""
    compose_sha256, image_digests = stack.facts()
    return StackFacts(
        compose_sha256=compose_sha256,
        image_digests=image_digests,
        api_version=api_version_payload(client),
    )


def api_version_payload(client: FactsClient) -> dict[str, object]:
    """``GET /openapi.json`` → ``info.version`` (map §5, OPEN-1)."""
    response = client.request("GET", _OPENAPI_PATH)
    payload: object = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"{_OPENAPI_PATH}: response is not a JSON object")
    body = cast("dict[str, object]", payload)
    raw_info = body.get("info")
    if not isinstance(raw_info, dict):
        raise RuntimeError(f"{_OPENAPI_PATH}: 'info' missing or not an object")
    info = cast("dict[str, object]", raw_info)
    version = info.get("version")
    if not isinstance(version, str) or not version:
        raise RuntimeError(f"{_OPENAPI_PATH}: 'info.version' missing or not a string")
    return {"source": "GET /openapi.json info.version", "version": version}
