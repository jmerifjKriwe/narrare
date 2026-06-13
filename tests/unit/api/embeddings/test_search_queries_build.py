"""Unit tests for embedding *build* query functions.

Split from ``test_search_queries.py`` to comply with RULE-04 file-size limits.

Covers:
- ``build_get_by_source_query`` — SQL with/without model filter
- ``build_batch_upsert_query`` — SQL for batch upsert
"""

from __future__ import annotations

from uuid import uuid4

from narrare.embeddings.search_queries import (
    build_batch_upsert_query,
    build_get_by_source_query,
)

# ---------------------------------------------------------------------------
# build_get_by_source_query
# ---------------------------------------------------------------------------


class TestBuildGetBySourceQuery:
    """build_get_by_source_query builds SELECT with optional model filter."""

    def test_build_get_by_source_query_no_model(self) -> None:
        """Without model, only source_type + source_id are filtered."""
        source_id = uuid4()
        sql, params = build_get_by_source_query("kb_entry", source_id)
        sql_str = str(sql)
        assert "source_type = :source_type" in sql_str
        assert "source_id = :source_id" in sql_str
        assert ":model" not in sql_str
        assert params["source_type"] == "kb_entry"
        assert params["source_id"] == str(source_id)

    def test_build_get_by_source_query_with_model(self) -> None:
        """With model, a model filter is added to the WHERE clause."""
        source_id = uuid4()
        sql, params = build_get_by_source_query(
            "kb_entry", source_id, model="text-embedding-3-small"
        )
        sql_str = str(sql)
        assert "source_type = :source_type" in sql_str
        assert "source_id = :source_id" in sql_str
        assert "model = :model" in sql_str
        assert params["model"] == "text-embedding-3-small"

    def test_build_get_by_source_query_produces_valid_sql(self) -> None:
        """Core SELECT structure."""
        source_id = uuid4()
        sql, _params = build_get_by_source_query("kb_entry", source_id)
        sql_str = str(sql)
        assert "SELECT" in sql_str
        assert "FROM embeddings" in sql_str
        assert "WHERE" in sql_str


# ---------------------------------------------------------------------------
# build_batch_upsert_query
# ---------------------------------------------------------------------------


class TestBuildBatchUpsertQuery:
    """build_batch_upsert_query builds INSERT ON CONFLICT for multiple rows."""

    def test_build_batch_upsert_query_single_item(self) -> None:
        """Single item produces valid UPSERT SQL with one row."""
        sid = uuid4()
        items = [("kb_entry", sid, "hash123", [0.1, 0.2], "model1", 2)]
        sql, params = build_batch_upsert_query(items)
        sql_str = str(sql)

        assert "INSERT INTO embeddings" in sql_str
        assert "ON CONFLICT" in sql_str
        assert "gen_random_uuid()" in sql_str
        assert params["p0_st"] == "kb_entry"
        assert params["p0_sid"] == str(sid)
        assert params["p0_ch"] == "hash123"
        assert params["p0_vec"] == "[0.1,0.2]"
        assert params["p0_mdl"] == "model1"
        assert params["p0_dim"] == 2

    def test_build_batch_upsert_query_multiple_items(self) -> None:
        """Multiple items use unique parameter prefixes."""
        sid1 = uuid4()
        sid2 = uuid4()
        items = [
            ("kb_entry", sid1, "hash1", [0.1, 0.2], "model1", 2),
            ("chapter", sid2, "hash2", [0.3, 0.4, 0.5], "model2", 3),
        ]
        sql, params = build_batch_upsert_query(items)
        sql_str = str(sql)

        # Two sets of parameters
        assert params["p0_st"] == "kb_entry"
        assert params["p0_sid"] == str(sid1)
        assert params["p0_vec"] == "[0.1,0.2]"
        assert params["p1_st"] == "chapter"
        assert params["p1_sid"] == str(sid2)
        assert params["p1_vec"] == "[0.3,0.4,0.5]"
        assert params["p1_mdl"] == "model2"
        assert params["p1_dim"] == 3

        # SQL contains DO UPDATE SET for upsert
        assert "DO UPDATE SET" in sql_str
        assert "content_hash = EXCLUDED.content_hash" in sql_str
        assert "embedding = EXCLUDED.embedding" in sql_str

    def test_build_batch_upsert_query_sql_structure(self) -> None:
        """Verify the generated SQL has correct structure."""
        items = [("kb_entry", uuid4(), "h", [0.1], "m", 1)]
        sql, _params = build_batch_upsert_query(items)
        sql_str = str(sql)

        assert sql_str.startswith("INSERT INTO embeddings")
        assert "VALUES" in sql_str
        assert "ON CONFLICT" in sql_str
        assert "now()" in sql_str
