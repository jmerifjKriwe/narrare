"""Unit tests for core/embeddings/rerank.py (ADR-090) — fake-based, no ST download.

The sentence-transformers surface is faked at the ``sys.modules`` boundary
(same pattern as ``tests/unit/core/nlp/test_provider_spacy_processing.py``),
so no checkpoint is ever downloaded (~600 MB, ADR-090) and the contract
tests run identically with or without the ``embeddings`` extra installed.

Interface per ADR-090 Decision 3 (the ADR wins over plan sketches where
they differ): ``Reranker.rerank(query, candidates, *, top_n)`` returning
sorted candidates; pure ``rerank_candidates`` reorder helper; pinned
default checkpoint (never the ST library default); lazy process-wide
encoder singleton keyed by model name (Decision 6).

Test contract (ADR-090 "Implementation Notes"): fake-encoder tests for the
MultiVector path; ``is_rerank_available()`` both ways; NullReranker
passthrough; real-checkpoint integration is pilot (Task 16) territory,
not CI.
"""

from __future__ import annotations

import sys
import types
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from narrare_core.embeddings import (
    DEFAULT_RERANK_MODEL,
    MultiVectorReranker,
    NullReranker,
    RerankCandidate,
    Reranker,
    is_rerank_available,
    rerank_candidates,
)
from narrare_core.embeddings import rerank as rerank_module

if TYPE_CHECKING:
    from collections.abc import Sequence

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _candidate(text: str, base_score: float, *, source_type: str = "kb_entry") -> RerankCandidate:
    """Build a RerankCandidate with the ADR-090 Decision-3 field set."""
    return RerankCandidate(
        source_id=uuid4(), source_type=source_type, text=text, base_score=base_score
    )


class FakeMultiVectorEncoder:
    """ADR-030 fake of ST v6 ``MultiVectorEncoder`` — records calls, no download.

    ``similarity`` returns ``[scores]`` — a ``[1, K]`` row (one query
    against K documents), indexable and iterable like the real Tensor.
    """

    def __init__(self) -> None:
        self.query_inputs: list[list[str]] = []
        self.document_inputs: list[list[str]] = []
        self.similarity_inputs: list[tuple[object, object]] = []
        self.scores: list[float] = []

    def encode_query(self, inputs: Sequence[str], **_kwargs: Any) -> list[str]:
        self.query_inputs.append(list(inputs))
        return [f"q:{text}" for text in inputs]

    def encode_document(self, inputs: Sequence[str], **_kwargs: Any) -> list[str]:
        self.document_inputs.append(list(inputs))
        return [f"d:{text}" for text in inputs]

    def similarity(
        self, embeddings1: object, embeddings2: object, **_kwargs: Any
    ) -> list[list[float]]:
        self.similarity_inputs.append((embeddings1, embeddings2))
        return [list(self.scores)]


class _FakeEncoderFactory:
    """Stand-in for the ``MultiVectorEncoder`` symbol — counts constructions."""

    def __init__(self) -> None:
        self.encoder = FakeMultiVectorEncoder()
        self.calls: list[str | None] = []

    def __call__(
        self, model_name_or_path: str | None = None, **_kwargs: Any
    ) -> FakeMultiVectorEncoder:
        self.calls.append(model_name_or_path)
        return self.encoder


class _FakeSentenceTransformersModule(types.ModuleType):
    """``sentence_transformers`` stand-in exposing the fake encoder factory.

    A ModuleType subclass so attribute injection needs no type suppression
    (RULE-23).
    """

    def __init__(self, factory: _FakeEncoderFactory) -> None:
        super().__init__("sentence_transformers")
        self.MultiVectorEncoder = factory


@pytest.fixture
def fake_st(monkeypatch: pytest.MonkeyPatch) -> _FakeEncoderFactory:
    """Inject a fake ``sentence_transformers`` module; reset the encoder cache."""
    factory = _FakeEncoderFactory()
    monkeypatch.setitem(
        sys.modules, "sentence_transformers", _FakeSentenceTransformersModule(factory)
    )
    monkeypatch.setattr(rerank_module, "_encoder_cache", {})
    return factory


@pytest.fixture
def no_st(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``import sentence_transformers`` raise ImportError.

    A ``None`` entry in ``sys.modules`` is the CPython-sanctioned way to
    block an import — it covers both the fresh-import and the
    already-cached path (the real extra is installed in this venv).
    """
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)


# ---------------------------------------------------------------------------
# RerankCandidate
# ---------------------------------------------------------------------------


class TestRerankCandidate:
    """RerankCandidate frozen dataclass (ADR-090 Decision 3)."""

    def test_carries_adr_fields(self) -> None:
        candidate = RerankCandidate(
            source_id=uuid4(), source_type="kb_entry", text="t", base_score=0.5
        )
        assert candidate.source_type == "kb_entry"
        assert candidate.text == "t"
        assert candidate.base_score == 0.5

    def test_frozen_and_hashable(self) -> None:
        """Frozen → value equality and hashability (unhashable if not frozen)."""
        source_id = uuid4()
        first = RerankCandidate(
            source_id=source_id, source_type="kb_entry", text="t", base_score=0.5
        )
        second = RerankCandidate(
            source_id=source_id, source_type="kb_entry", text="t", base_score=0.5
        )
        assert first == second
        assert hash(first) == hash(second)


# ---------------------------------------------------------------------------
# NullReranker
# ---------------------------------------------------------------------------


class TestNullReranker:
    """NullReranker passthrough — input order, truncated to top_n."""

    async def test_rerank_preserves_input_order_and_truncates(self) -> None:
        """Base scores are deliberately NOT in input order — passthrough
        must not re-sort by them."""
        candidates = [_candidate("a", 0.9), _candidate("b", 0.1), _candidate("c", 0.5)]
        ranked = await NullReranker().rerank("q", candidates, top_n=2)
        assert [c.text for c in ranked] == ["a", "b"]

    async def test_rerank_top_n_beyond_length_returns_all(self) -> None:
        candidates = [_candidate("a", 0.2), _candidate("b", 0.1)]
        ranked = await NullReranker().rerank("q", candidates, top_n=10)
        assert ranked == candidates

    async def test_rerank_empty_candidates_returns_empty(self) -> None:
        assert await NullReranker().rerank("q", [], top_n=5) == []

    async def test_rerank_negative_top_n_raises(self) -> None:
        with pytest.raises(ValueError, match="top_n"):
            await NullReranker().rerank("q", [_candidate("a", 0.5)], top_n=-1)

    def test_satisfies_reranker_protocol(self) -> None:
        assert isinstance(NullReranker(), Reranker)


# ---------------------------------------------------------------------------
# rerank_candidates — pure reorder helper
# ---------------------------------------------------------------------------


class TestRerankCandidates:
    """Pure reorder: stable sort by score desc, optional top-keep."""

    async def test_sorts_by_rerank_score_desc(self) -> None:
        candidates = [_candidate("a", 0.9), _candidate("b", 0.1), _candidate("c", 0.5)]
        ranked = await rerank_candidates(candidates, [0.1, 0.9, 0.5])
        assert [c.text for c in ranked] == ["b", "c", "a"]

    async def test_keep_truncates_after_sort(self) -> None:
        candidates = [_candidate("a", 0.9), _candidate("b", 0.1)]
        ranked = await rerank_candidates(candidates, [0.2, 0.8], keep=1)
        assert [c.text for c in ranked] == ["b"]

    async def test_stable_order_on_ties(self) -> None:
        candidates = [_candidate("a", 0.9), _candidate("b", 0.9)]
        ranked = await rerank_candidates(candidates, [0.5, 0.5])
        assert [c.text for c in ranked] == ["a", "b"]

    async def test_keep_none_returns_all(self) -> None:
        candidates = [_candidate("a", 0.9), _candidate("b", 0.1)]
        ranked = await rerank_candidates(candidates, [0.2, 0.8])
        assert [c.text for c in ranked] == ["b", "a"]

    async def test_empty_candidates_returns_empty(self) -> None:
        assert await rerank_candidates([], []) == []

    async def test_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="candidates"):
            await rerank_candidates([_candidate("a", 0.5)], [0.1, 0.2])

    async def test_negative_keep_raises(self) -> None:
        with pytest.raises(ValueError, match="keep"):
            await rerank_candidates([_candidate("a", 0.5)], [0.1], keep=-1)


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


class TestAvailability:
    """is_rerank_available() both ways; absent-extra construction contract."""

    def test_returns_bool(self) -> None:
        assert isinstance(is_rerank_available(), bool)

    def test_returns_true_when_st_importable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(
            sys.modules, "sentence_transformers", types.ModuleType("sentence_transformers")
        )
        assert is_rerank_available() is True

    def test_returns_false_when_st_missing(self, no_st: None) -> None:
        assert is_rerank_available() is False

    def test_multivector_reranker_absent_extra_degrades(self) -> None:
        """When ST is missing, MultiVectorReranker construction raises
        ImportError with a pointed message (RULE-11 graceful degradation
        contract); with ST installed (this venv), availability must be True."""
        try:
            MultiVectorReranker()
        except ImportError as exc:
            assert "embeddings" in str(exc)
        else:
            assert is_rerank_available() is True

    def test_constructor_without_extra_raises_import_error(self, no_st: None) -> None:
        with pytest.raises(ImportError, match="embeddings"):
            MultiVectorReranker()


# ---------------------------------------------------------------------------
# Degraded path — contract usable without the extra
# ---------------------------------------------------------------------------


class TestDegradedPathWithoutExtra:
    """NullReranker + rerank_candidates work with ST unimportable."""

    async def test_null_reranker_works_without_st(self, no_st: None) -> None:
        candidates = [_candidate("a", 0.9), _candidate("b", 0.1)]
        ranked = await NullReranker().rerank("q", candidates, top_n=1)
        assert [c.text for c in ranked] == ["a"]

    async def test_rerank_candidates_works_without_st(self, no_st: None) -> None:
        ranked = await rerank_candidates([_candidate("a", 0.9)], [0.5], keep=1)
        assert [c.text for c in ranked] == ["a"]


# ---------------------------------------------------------------------------
# MultiVectorReranker — fake-encoder tests (no checkpoint download)
# ---------------------------------------------------------------------------


class TestMultiVectorReranker:
    """MultiVectorReranker against a faked sentence-transformers surface."""

    def test_construction_does_not_load_checkpoint(self, fake_st: _FakeEncoderFactory) -> None:
        """Lazy first-use load (ADR-090 Decision 6): construction probes
        availability only — no encoder instantiation, no download."""
        MultiVectorReranker()
        assert fake_st.calls == []

    async def test_rerank_orders_by_maxsim_scores_and_truncates(
        self, fake_st: _FakeEncoderFactory
    ) -> None:
        fake_st.encoder.scores = [0.1, 0.9, 0.5]
        candidates = [_candidate("a", 0.9), _candidate("b", 0.1), _candidate("c", 0.5)]
        ranked = await MultiVectorReranker().rerank("query", candidates, top_n=2)
        assert [c.text for c in ranked] == ["b", "c"]

    async def test_rerank_uses_binding_call_sequence(self, fake_st: _FakeEncoderFactory) -> None:
        """ADR-090 binding call sequence: encode_query([query]),
        encode_document(texts), similarity(query, documents)."""
        fake_st.encoder.scores = [0.7]
        candidates = [_candidate("a", 0.5)]
        await MultiVectorReranker().rerank("the query", candidates, top_n=1)
        encoder = fake_st.encoder
        assert encoder.query_inputs == [["the query"]]
        assert encoder.document_inputs == [["a"]]
        assert len(encoder.similarity_inputs) == 1
        query_embeddings, document_embeddings = encoder.similarity_inputs[0]
        assert query_embeddings == ["q:the query"]
        assert document_embeddings == ["d:a"]

    async def test_default_checkpoint_is_adr_pinned(self, fake_st: _FakeEncoderFactory) -> None:
        """Default model = the pinned checkpoint (ADR-090 Decision 5) —
        never the ST library default."""
        assert DEFAULT_RERANK_MODEL == "lightonai/LateOn"
        fake_st.encoder.scores = [0.3]
        await MultiVectorReranker().rerank("q", [_candidate("a", 0.5)], top_n=1)
        assert fake_st.calls == ["lightonai/LateOn"]

    async def test_explicit_model_name_reaches_encoder(self, fake_st: _FakeEncoderFactory) -> None:
        fake_st.encoder.scores = [0.3]
        reranker = MultiVectorReranker("org/other-reranker")
        await reranker.rerank("q", [_candidate("a", 0.5)], top_n=1)
        assert fake_st.calls == ["org/other-reranker"]

    async def test_encoder_loaded_once_across_calls(self, fake_st: _FakeEncoderFactory) -> None:
        """Process-wide singleton keyed by model name (Decision 6): two
        rerank calls load the encoder once."""
        fake_st.encoder.scores = [0.4]
        reranker = MultiVectorReranker()
        await reranker.rerank("q1", [_candidate("a", 0.5)], top_n=1)
        await reranker.rerank("q2", [_candidate("b", 0.4)], top_n=1)
        assert len(fake_st.calls) == 1

    async def test_encoder_singleton_shared_across_instances(
        self, fake_st: _FakeEncoderFactory
    ) -> None:
        """The cache is module-level (process-wide), not per instance."""
        fake_st.encoder.scores = [0.4]
        await MultiVectorReranker("m/x").rerank("q", [_candidate("a", 0.5)], top_n=1)
        await MultiVectorReranker("m/x").rerank("q", [_candidate("b", 0.4)], top_n=1)
        assert fake_st.calls == ["m/x"]

    async def test_distinct_model_names_load_distinct_encoders(
        self, fake_st: _FakeEncoderFactory
    ) -> None:
        fake_st.encoder.scores = [0.4]
        for model_name in ("m/one", "m/two"):
            await MultiVectorReranker(model_name).rerank("q", [_candidate("a", 0.5)], top_n=1)
        assert fake_st.calls == ["m/one", "m/two"]

    async def test_empty_candidates_skip_encoder_load(self, fake_st: _FakeEncoderFactory) -> None:
        """No candidates → no encoder load, no download."""
        ranked = await MultiVectorReranker().rerank("q", [], top_n=5)
        assert ranked == []
        assert fake_st.calls == []

    async def test_rerank_negative_top_n_raises(self, fake_st: _FakeEncoderFactory) -> None:
        with pytest.raises(ValueError, match="top_n"):
            await MultiVectorReranker().rerank("q", [_candidate("a", 0.5)], top_n=-1)
        assert fake_st.calls == []  # fails before any encoder load

    def test_satisfies_reranker_protocol(self, fake_st: _FakeEncoderFactory) -> None:
        assert isinstance(MultiVectorReranker(), Reranker)
