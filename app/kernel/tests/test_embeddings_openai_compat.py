"""The OpenAI-shaped embedding strategy: a real socket, real JSON, no vendor key.

The response shape is the one the vendors share — ``{"data": [{"embedding": [...],
"index": n}]}``. The width is whatever the model answers: the column stores any
width, and the corpus guard — not the schema — keeps one knowledge base
consistent. A configured ``dimensions`` is a truncation hint for vendors that
support one, never a requirement.
"""

import json

import httpx
import pytest

from app.kernel.embeddings.openai_compat import (
    OpenAICompatibleEmbeddingProvider,
    OpenAIEmbeddingSettings,
)
from app.kernel.tests.vendor_server import vendor_server

TEXTS = ["Der Leuchtturm war dunkel.", "Der Nebel hob sich vom See."]


def _vector(seed: float, width: int) -> list[float]:
    return [seed] * width


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
    dimensions: int | None = None,
) -> OpenAICompatibleEmbeddingProvider:
    return OpenAICompatibleEmbeddingProvider(
        OpenAIEmbeddingSettings(
            base_url=base_url, model=model, api_key=api_key, dimensions=dimensions
        )
    )


async def test_one_vector_per_text_comes_back_in_the_order_of_the_texts() -> None:
    # The vendor answers in its own order and at its native width; the strategy
    # owes the caller the order of its input, because the caller pairs vectors
    # with chunks by index.
    reversed_indices = [1, 0]
    with vendor_server(
        body=_response([_vector(2.0, 768), _vector(1.0, 768)], indices=reversed_indices)
    ) as vendor:
        vectors = await _provider(vendor.base_url).embed(TEXTS)

    assert len(vectors) == 2
    assert all(len(vector) == 768 for vector in vectors)
    assert vectors[0][0] == 1.0
    assert vectors[1][0] == 2.0


async def test_no_dimensions_hint_means_the_models_native_width() -> None:
    with vendor_server(body=_response([_vector(1.0, 1536), _vector(2.0, 1536)])) as vendor:
        vectors = await _provider(vendor.base_url).embed(TEXTS)
        sent = vendor.last

    assert all(len(vector) == 1536 for vector in vectors)
    assert "dimensions" not in sent["body"]


async def test_a_configured_dimensions_hint_is_sent_to_the_vendor() -> None:
    # A truncation-capable vendor (OpenAI's v3 models) can be asked for less
    # than its native width; that is a storage choice, not a schema constraint.
    with vendor_server(body=_response([_vector(1.0, 384), _vector(2.0, 384)])) as vendor:
        await _provider(vendor.base_url, dimensions=384).embed(TEXTS)

    assert vendor.last["body"]["dimensions"] == 384


async def test_the_request_carries_model_input_and_key() -> None:
    with vendor_server(body=_response([_vector(1.0, 384), _vector(2.0, 384)])) as vendor:
        await _provider(vendor.base_url).embed(TEXTS)
        sent = vendor.last

    assert sent["path"] == "/v1/embeddings"
    assert sent["body"]["model"] == "test-embedding-model"
    assert sent["body"]["input"] == TEXTS
    assert sent["headers"]["Authorization"] == "Bearer test-key"


async def test_a_response_of_mixed_widths_raises() -> None:
    # The caller stores the vectors in one column and compares them against one
    # query; two widths in one batch would corrupt the corpus silently.
    mixed = json.dumps(
        {
            "data": [
                {"index": 0, "embedding": _vector(1.0, 384)},
                {"index": 1, "embedding": _vector(1.0, 768)},
            ]
        }
    )
    with (
        vendor_server(body=mixed) as vendor,
        pytest.raises(RuntimeError, match="width"),
    ):
        await _provider(vendor.base_url).embed(TEXTS)


async def test_a_response_of_another_count_than_the_texts_raises() -> None:
    short = _response([_vector(1.0, 384)])
    with (
        vendor_server(body=short) as vendor,
        pytest.raises(RuntimeError, match="2 texts"),
    ):
        await _provider(vendor.base_url).embed(TEXTS)


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
        base_url="https://api.openai.com/v1", model="", api_key="", dimensions=None
    )
    assert any("NARRE_EMBEDDING_MODEL" in problem for problem in settings.problems())
    assert any("NARRE_EMBEDDING_API_KEY" in problem for problem in settings.problems())


def test_a_local_provider_needs_no_key() -> None:
    settings = OpenAIEmbeddingSettings(
        base_url="http://localhost:11434/v1",
        model="nomic-embed-text",
        api_key="",
        dimensions=None,
    )
    assert settings.problems() == []


def test_the_description_names_the_model_and_the_endpoint() -> None:
    described = _provider("https://api.openai.com/v1", model="text-embedding-3-small").describe()
    assert "openai-compatible" in described
    assert "text-embedding-3-small" in described
    assert "api.openai.com" in described


def test_the_description_names_a_configured_truncation_hint() -> None:
    described = _provider(
        "https://api.openai.com/v1", model="text-embedding-3-small", dimensions=384
    ).describe()
    assert "dimensions=384" in described
