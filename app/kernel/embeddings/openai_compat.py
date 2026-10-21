"""Fetch strategy for the OpenAI-shaped embeddings API, answered as JSON.

One shape covers OpenAI, Azure-compatible gateways, OpenRouter's embedding
routes and local servers (Ollama, llama.cpp, vLLM): they differ in base URL,
model and key, not in protocol. A vendor with a different protocol gets its own
module next to this one.

The database column fixes the width, so the request asks the model for it
(``dimensions`` on OpenAI's v3 models). A vendor that answers another width is a
configuration mistake that cannot be stored: it raises with the two ways out
instead of failing later inside pgvector.
"""

from collections.abc import Sequence  # noqa: TC003
from dataclasses import dataclass
from os import environ
from typing import Any

import httpx

from app.kernel.embeddings.contract import SCHEMA_DIMENSIONS
from app.kernel.vendor import needs_api_key

DEFAULT_BASE_URL = "https://api.openai.com/v1"

TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
"""Batch embedding is request/response, not a stream: a minute is generous."""


@dataclass(frozen=True)
class OpenAIEmbeddingSettings:
    """Where to send the texts. Read from the environment, or passed in tests."""

    base_url: str
    model: str
    api_key: str
    dimensions: int

    @classmethod
    def from_environment(cls) -> OpenAIEmbeddingSettings:
        return cls(
            base_url=environ.get("NARRE_EMBEDDING_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            model=environ.get("NARRE_EMBEDDING_MODEL", ""),
            api_key=environ.get("NARRE_EMBEDDING_API_KEY", ""),
            dimensions=int(environ.get("NARRE_EMBEDDING_DIMENSIONS", str(SCHEMA_DIMENSIONS))),
        )

    def problems(self) -> list[str]:
        """What this entry needs but does not have; empty when it is ready."""
        problems: list[str] = []
        if not self.model:
            problems.append("NARRE_EMBEDDING_MODEL is not set")
        if not self.api_key and needs_api_key(self.base_url):
            problems.append("NARRE_EMBEDDING_API_KEY is not set (a remote endpoint needs one)")
        return problems


class OpenAICompatibleEmbeddingProvider:
    """Embeds texts through any OpenAI-shaped ``/embeddings`` endpoint."""

    def __init__(self, settings: OpenAIEmbeddingSettings) -> None:
        self.settings = settings
        self.dimensions = settings.dimensions

    @classmethod
    def from_environment(cls) -> OpenAICompatibleEmbeddingProvider:
        """The catalog's factory: configuration comes from the environment."""
        return cls(OpenAIEmbeddingSettings.from_environment())

    def describe(self) -> str:
        # The startup line names the width once, from the instance's validated
        # environment; the request itself carries it to the vendor.
        return (
            f"openai-compatible model={self.settings.model or '(unset)'}"
            f" base_url={self.settings.base_url}"
        )

    def configuration_problems(self) -> list[str]:
        return self.settings.problems()

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        headers = (
            {"Authorization": f"Bearer {self.settings.api_key}"} if self.settings.api_key else {}
        )
        body = {
            "model": self.settings.model,
            "input": list(texts),
            "dimensions": self.settings.dimensions,
        }
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{self.settings.base_url}/embeddings", json=body, headers=headers
            )
            response.raise_for_status()
        payload: Any = response.json()
        return self._vectors(payload, len(texts))

    def _vectors(self, payload: Any, expected: int) -> list[list[float]]:
        """The vectors in the order of the texts, or a refusal that names the fix.

        Vendors may answer in their own order, so the ``index`` decides; the
        caller pairs vectors with chunks by position and would otherwise store
        every chunk under another chunk's meaning.
        """
        rows = sorted(payload["data"], key=lambda row: row["index"])
        vectors: list[list[float]] = [row["embedding"] for row in rows]
        if len(vectors) != expected:
            raise RuntimeError(
                f"the embedding vendor returned {len(vectors)} vectors for {expected} texts"
            )
        for vector in vectors:
            if len(vector) != self.settings.dimensions:
                raise RuntimeError(
                    f"the embedding vendor returned {len(vector)} dimensions, the schema has"
                    f" {self.settings.dimensions}: ask the model for"
                    f" {self.settings.dimensions} dimensions, or change the width with a"
                    " migration"
                )
        return vectors
