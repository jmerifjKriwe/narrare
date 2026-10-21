"""The OpenAI-shaped embedding strategy: a real socket, real JSON, no vendor key.

The response shape is the one the vendors share — ``{"data": [{"embedding": [...],
"index": n}]}`` — and the width is the width the database column has, so a real
model has to be asked for it (``dimensions`` on the request).
"""

import json

import httpx
import pytest

from app.kernel.embeddings import SCHEMA_DIMENSIONS
from app.kernel.embeddings.openai_compat import (
    OpenAICompatibleEmbeddingProvider,
    OpenAIEmbeddingSettings,
)
from app.kernel.tests.vendor_server import vendor_server

TEXTS = ["Der Leuchtturm war dunkel.", "Der Nebel hob sich vom See."]


def _vector(seed: float) -> list[float]:
    return [seed] * SCHEMA_DIMENSIONS


def _response(vectors: list[list[float]], *, indices: list[int] | None = None) -> str:
    order = indices if indices is not None else list(range(len(vectors)))
    return json.dumps(
        {
            "data": [
                {"object": "embedding", "index": index, "embedding": vector}
                for index, vector in zip(order, vectors, strict=True)
            ],
            "model": "test-embedding-model",
        }
    )


def _provider(
    base_url: str,
    model: str = "test-embedding-model",
    api_key: str = "test-key",
    dimensions: int = SCHEMA_DIMENSIONS,
) -> OpenAICompatibleEmbeddingProvider:
    return OpenAICompatibleEmbeddingProvider(
        OpenAIEmbeddingSettings(
            base_url=base_url, model=model, api_key=api_key, dimensions=dimensions
        )
    )


async def test_one_vector_per_text_comes_back_in_the_order_of_the_texts() -> None:
    # The vendor answers in its own order; the strategy owes the caller the
    # order of its input, because the caller pairs vectors with chunks by index.
    reversed_indices = [1, 0]
    with vendor_server(
        body=_response([_vector(2.0), _vector(1.0)], indices=reversed_indices)
    ) as vendor:
        vectors = await _provider(vendor.base_url).embed(TEXTS)

    assert len(vectors) == 2
    assert vectors[0][0] == 1.0
    assert vectors[1][0] == 2.0
    assert all(len(vector) == SCHEMA_DIMENSIONS for vector in vectors)


async def test_the_request_carries_model_input_width_and_key() -> None:
    with vendor_server(body=_response([_vector(1.0), _vector(2.0)])) as vendor:
        await _provider(vendor.base_url).embed(TEXTS)
        sent = vendor.last

    assert sent["path"] == "/v1/embeddings"
    assert sent["body"]["model"] == "test-embedding-model"
    assert sent["body"]["input"] == TEXTS
    assert sent["body"]["dimensions"] == SCHEMA_DIMENSIONS
    assert sent["headers"]["Authorization"] == "Bearer test-key"


async def test_a_response_of_another_width_raises_a_clear_error() -> None:
    wrong_width = json.dumps({"data": [{"index": 0, "embedding": [1.0, 2.0, 3.0]}]})
    with (
        vendor_server(body=wrong_width) as vendor,
        pytest.raises(RuntimeError, match="migration"),
    ):
        await _provider(vendor.base_url).embed(TEXTS[:1])


async def test_no_texts_means_no_request() -> None:
    with vendor_server(body=_response([])) as vendor:
        assert await _provider(vendor.base_url).embed([]) == []
        assert vendor.received == []


async def test_a_refused_request_raises() -> None:
    refusal = json.dumps({"error": {"message": "Incorrect API key provided"}})
    with (
        vendor_server(body=refusal, status=401) as vendor,
        pytest.raises(httpx.HTTPStatusError),
    ):
        await _provider(vendor.base_url).embed(TEXTS[:1])


def test_a_remote_provider_without_a_key_reports_what_it_needs() -> None:
    settings = OpenAIEmbeddingSettings(
        base_url="https://api.openai.com/v1",
        model="",
        api_key="",
        dimensions=SCHEMA_DIMENSIONS,
    )
    assert any("NARRE_EMBEDDING_MODEL" in problem for problem in settings.problems())
    assert any("NARRE_EMBEDDING_API_KEY" in problem for problem in settings.problems())


def test_a_local_provider_needs_no_key() -> None:
    settings = OpenAIEmbeddingSettings(
        base_url="http://localhost:11434/v1",
        model="nomic-embed-text",
        api_key="",
        dimensions=SCHEMA_DIMENSIONS,
    )
    assert settings.problems() == []


def test_the_description_names_the_model_and_the_endpoint() -> None:
    described = _provider("https://api.openai.com/v1", model="text-embedding-3-small").describe()
    assert "openai-compatible" in described
    assert "text-embedding-3-small" in described
    assert "api.openai.com" in described
    # The width is asserted where it acts: on the request the strategy sends.
