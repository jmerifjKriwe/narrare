"""Unit tests for embedding search query builders.

Tests the pure SQL builder functions in ``search_queries.py``.
No DB connection needed — these are pure string/parameter assembly functions.

Test matrix:
- ``build_vector_str`` — pgvector string format
- ``parse_embedding_row`` — tuple → Embedding conversion
- ``parse_search_row`` — tuple → SearchRow with None handling
- ``build_search_query`` — SQL with optional filter combinations
- ``build_get_by_source_query`` — SQL with/without model filter
- ``build_batch_upsert_query`` — SQL for batch upsert
"""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from narrare.embeddings.models import Embedding
from narrare.embeddings.search_queries import (
    SearchRow,
    build_search_query,
    build_vector_str,
    parse_embedding_row,
    parse_search_row,
)

# ---------------------------------------------------------------------------
# build_vector_str
# ---------------------------------------------------------------------------


class TestBuildVectorStr:
    """build_vector_str converts float lists to pgvector format."""

    def test_build_vector_str_standard_list(self) -> None:
        """[0.1, 0.2, 0.3] → ``[0.1,0.2,0.3]``."""
        result = build_vector_str([0.1, 0.2, 0.3])
        assert result == "[0.1,0.2,0.3]"

    def test_build_vector_str_empty_list(self) -> None:
        """Empty list → ``[]``."""
        result = build_vector_str([])
        assert result == "[]"

    def test_build_vector_str_single_element(self) -> None:
        """Single float → ``[42.0]``."""
        result = build_vector_str([42.0])
        assert result == "[42.0]"

    def test_build_vector_str_negative_values(self) -> None:
        """Negative floats are included correctly."""
        result = build_vector_str([-0.5, 0.0, 0.5])
        assert result == "[-0.5,0.0,0.5]"


# ---------------------------------------------------------------------------
# parse_embedding_row
# ---------------------------------------------------------------------------


class TestParseEmbeddingRow:
    """parse_embedding_row converts a raw SQL row tuple to an Embedding model."""

    def test_parse_embedding_row_all_fields(self) -> None:
        """All 8 fields are correctly mapped to Embedding attributes."""
        now = datetime.now()
        emb_id = uuid4()
        source_id = uuid4()
        row: tuple[object, ...] = (
            emb_id,
            "kb_entry",
            source_id,
            "abc123def",
            [0.1, 0.2, 0.3],
            "text-embedding-3-small",
            1536,
            now,
        )
        result = parse_embedding_row(row)

        assert isinstance(result, Embedding)
        assert result.id == emb_id
        assert result.source_type == "kb_entry"
        assert result.source_id == source_id
        assert result.content_hash == "abc123def"
        assert result.embedding == [0.1, 0.2, 0.3]
        assert result.model == "text-embedding-3-small"
        assert result.dimension == 1536
        assert result.generated_at == now

    def test_parse_embedding_row_source_id_is_uuid(self) -> None:
        """source_id remains UUID type after parsing."""
        source_id = uuid4()
        row: tuple[object, ...] = (
            uuid4(),
            "chapter",
            source_id,
            "hash",
            [0.0] * 4,
            "test-model",
            4,
            datetime.now(),
        )
        result = parse_embedding_row(row)
        assert isinstance(result.source_id, UUID)
        assert result.source_id == source_id


# ---------------------------------------------------------------------------
# parse_search_row
# ---------------------------------------------------------------------------


class TestParseSearchRow:
    """parse_search_row converts raw SQL row to SearchRow with None handling."""

    def test_parse_search_row_all_values_present(self) -> None:
        """Happy path: all fields including metadata have real values."""
        now = datetime.now()
        source_id = uuid4()
        row: tuple[object, ...] = (
            uuid4(),
            "kb_entry",
            source_id,
            "hash",
            [0.1] * 4,
            "text-embedding-3-small",
            4,
            now,
            0.95,
            5,
            now,
        )
        result = parse_search_row(row)

        assert isinstance(result, SearchRow)
        assert isinstance(result.embedding, Embedding)
        assert result.similarity == 0.95
        assert result.usage_count == 5
        assert result.last_referenced_at == now

    def test_parse_search_row_null_similarity_defaults_to_zero(self) -> None:
        """When similarity is None, defaults to 0.0."""
        now = datetime.now()
        row: tuple[object, ...] = (
            uuid4(),
            "kb_entry",
            uuid4(),
            "hash",
            [0.1] * 4,
            "model",
            4,
            now,
            None,
            0,
            None,
        )
        result = parse_search_row(row)
        assert result.similarity == 0.0

    def test_parse_search_row_null_usage_defaults_to_zero(self) -> None:
        """When usage_count is None, defaults to 0."""
        now = datetime.now()
        row: tuple[object, ...] = (
            uuid4(),
            "kb_entry",
            uuid4(),
            "hash",
            [0.1] * 4,
            "model",
            4,
            now,
            0.85,
            None,
            None,
        )
        result = parse_search_row(row)
        assert result.usage_count == 0
        assert result.similarity == 0.85

    def test_parse_search_row_last_referenced_at(self) -> None:
        """last_referenced_at defaults to None when not a datetime."""
        now = datetime.now()
        # row[10] is None → last_referenced_at should be None
        row: tuple[object, ...] = (
            uuid4(),
            "kb_entry",
            uuid4(),
            "hash",
            [0.1] * 4,
            "model",
            4,
            now,
            0.9,
            3,
            None,
        )
        result = parse_search_row(row)
        assert result.last_referenced_at is None

    def test_parse_search_row_returns_embedding_object(self) -> None:
        """The embedding field is a proper Embedding instance."""
        now = datetime.now()
        emb_id = uuid4()
        source_id = uuid4()
        row: tuple[object, ...] = (
            emb_id,
            "kb_entry",
            source_id,
            "hash",
            [0.5] * 4,
            "model-x",
            4,
            now,
            0.99,
            10,
            now,
        )
        result = parse_search_row(row)
        assert result.embedding.id == emb_id
        assert result.embedding.source_id == source_id
        assert result.embedding.model == "model-x"


# ---------------------------------------------------------------------------
# build_search_query
# ---------------------------------------------------------------------------


class TestBuildSearchQuery:
    """build_search_query builds SQL with optional filters."""

    def test_build_search_query_no_filters(self) -> None:
        """Default params: no source_type, no model, no source_ids."""
        sql, params = build_search_query("[0.1,0.2]")
        sql_str = str(sql)
        assert "<=>" in sql_str
        assert params["query_vec"] == "[0.1,0.2]"
        assert params["threshold"] == 0.7
        assert params["limit"] == 20
        # source_type appears in SELECT (e.source_type) but not as WHERE filter
        assert "source_type = :source_type" not in sql_str
        assert "model = :model" not in sql_str

    def test_build_search_query_with_source_type(self) -> None:
        """source_type filter is added to SQL."""
        sql, params = build_search_query("[0.1]", source_type="kb_entry")
        sql_str = str(sql)
        assert "source_type = :source_type" in sql_str
        assert params["source_type"] == "kb_entry"

    def test_build_search_query_with_model(self) -> None:
        """model filter is added to SQL."""
        sql, params = build_search_query("[0.1]", model="text-embedding-3-small")
        sql_str = str(sql)
        assert "model = :model" in sql_str
        assert params["model"] == "text-embedding-3-small"

    def test_build_search_query_with_source_ids(self) -> None:
        """source_ids filter adds ANY clause."""
        ids = {uuid4(), uuid4()}
        sql, params = build_search_query("[0.1]", source_ids=ids)
        sql_str = str(sql)
        assert "source_id = ANY(:source_ids)" in sql_str
        source_ids_param = cast("list[str]", params["source_ids"])
        assert set(source_ids_param) == {str(i) for i in ids}

    def test_build_search_query_custom_threshold(self) -> None:
        """Custom threshold is passed through."""
        _, params = build_search_query("[0.1]", threshold=0.5)
        assert params["threshold"] == 0.5

    def test_build_search_query_custom_limit(self) -> None:
        """Custom limit is passed through."""
        _, params = build_search_query("[0.1]", limit=10)
        assert params["limit"] == 10

    def test_build_search_query_all_filters_combined(self) -> None:
        """All filters combined produce correct SQL."""
        ids = {uuid4()}
        sql, params = build_search_query(
            "[0.1]",
            source_type="chapter",
            source_ids=ids,
            threshold=0.8,
            limit=5,
            model="test-model",
        )
        sql_str = str(sql)
        assert "source_type = :source_type" in sql_str
        assert "source_id = ANY(:source_ids)" in sql_str
        assert "model = :model" in sql_str
        assert "similarity DESC" in sql_str
        assert params["query_vec"] == "[0.1]"
        assert params["threshold"] == 0.8
        assert params["limit"] == 5
        assert params["source_type"] == "chapter"
        assert params["model"] == "test-model"

    def test_build_search_query_produces_valid_sql(self) -> None:
        """The generated SQL contains all required clauses."""
        sql, params = build_search_query("[0.1,0.2]", source_type="kb_entry")
        sql_str = str(sql)
        # Core clauses
        assert "SELECT" in sql_str
        assert "FROM embeddings" in sql_str
        assert "LEFT JOIN kb_entries" in sql_str
        assert "ORDER BY similarity DESC" in sql_str
        assert "LIMIT :limit" in sql_str
        # Parameterised values
        assert ":query_vec" in sql_str
        assert ":threshold" in sql_str
        assert "source_type = :source_type" in sql_str
        assert params["source_type"] == "kb_entry"

    def test_build_search_query_empty_source_ids_omits_filter(self) -> None:
        """Empty set of source_ids does not add ANY clause."""
        sql, _params = build_search_query("[0.1]", source_ids=set())
        sql_str = str(sql)
        assert "source_id = ANY" not in sql_str
