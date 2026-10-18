"""Unit tests for embedding *build* query functions.

Split from ``test_search_queries.py`` to comply with RULE-04 file-size limits.

Covers:
- ``build_get_by_source_query`` — SQL with/without model filter
- ``build_batch_upsert_query`` — SQL for batch upsert
"""

from __future__ import annotations

import inspect
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from narrare.embeddings import repository as repository_module
from narrare.embeddings import search_queries as search_queries_module
from narrare.embeddings.search_queries import (
    build_batch_upsert_query,
    build_get_by_source_query,
    build_search_query,
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
# build_search_query — NaN guard + novel scoping (ADR-088 suggestions)
# ---------------------------------------------------------------------------


class TestBuildSearchQueryScoping:
    """Zero-vector rows and cross-novel rows must never surface.

    A zero-vector stored embedding makes pgvector's ``<=>`` return NaN;
    Postgres orders NaN ABOVE every real number, so such rows passed the
    threshold with a NaN similarity and poisoned the KB suggestions
    response (pydantic ``ge=0.0`` rejected NaN → 500). ``novel_id``
    scoping closes the suggestions path' cross-novel leak (the store
    protocol documents it as required; the service dropped it).
    """

    def test_search_query_always_excludes_nan_distances(self) -> None:
        """The NaN guard is unconditional (no caller can opt out)."""
        sql, _params = build_search_query("[0.1]")
        sql_str = str(sql)
        assert "CAST('NaN' AS real)" in sql_str
        # CAST form only — a ``'NaN'::real`` literal trips the
        # ``:name::TYPE`` asyncpg bind-param bug.
        assert "::real" not in sql_str

    def test_search_query_without_novel_id_has_no_scope(self) -> None:
        """Without novel_id, no scope condition is emitted (notes path)."""
        sql, params = build_search_query("[0.1]")
        sql_str = str(sql)
        assert "novel_id" not in sql_str
        assert "novel_id" not in params

    def test_search_query_with_novel_id_scopes_to_kb_join(self) -> None:
        """With novel_id, the KB join must match (orphans excluded)."""
        novel = uuid4()
        sql, params = build_search_query("[0.1]", novel_id=novel)
        sql_str = str(sql)
        assert "kb.novel_id = :novel_id" in sql_str
        assert params["novel_id"] == str(novel)


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


# ---------------------------------------------------------------------------
# Regression: vector bind params must be CAST(), never ``:param::vector``
# ---------------------------------------------------------------------------


class TestVectorParamsAreBoundByDialect:
    """Regression guard for the ``:param::vector`` asyncpg/SQLAlchemy bug.

    SQLAlchemy's ``text()`` bind-param regex does NOT recognise ``:name`` when
    it is immediately followed by ``:`` (the ``::TYPE`` cast), so
    ``:v::vector`` is emitted as a literal and asyncpg raises
    ``PostgresSyntaxError: syntax error at or near ":"``. The dialect-safe
    form is ``CAST(:name AS vector)``.

    This bug stayed latent because the only tests exercising ``upsert``/
    ``search`` with real pgvector were hard-skipped (``skipif(True)`` in
    ``test_embedding_repository_crud.py``); ADR-080's in-process embedding hook
    surfaced it via the fire-and-forget task. These tests compile each vector
    query with the asyncpg dialect and assert the vector param is recognised
    (present in ``positiontup``) so the regression cannot silently return.
    """

    @staticmethod
    def _bound_keys(sql_text: object) -> set[str]:
        compiled = (
            sql_text.compile(dialect=postgresql.asyncpg.dialect())  # pyright: ignore[reportAttributeAccessIssue]
        )
        return set(compiled.positiontup)  # pyright: ignore[reportAttributeAccessIssue]

    def test_search_query_binds_query_vec(self) -> None:
        """``query_vec`` is a real bind param, not an inline ``::vector`` cast."""
        sql, _params = build_search_query("[0.1]", source_type="kb_entry", threshold=0.5, limit=5)
        assert "query_vec" in self._bound_keys(sql)
        rendered = str(sql.compile(dialect=postgresql.asyncpg.dialect()))
        # asyncpg renders the bind as ``$N``; CAST survives, ``::vector`` must not.
        assert "CAST(" in rendered
        assert "AS vector)" in rendered
        assert "::vector" not in rendered

    def test_batch_upsert_binds_each_vec(self) -> None:
        """Every batch row's ``pN_vec`` is a real bind param."""
        items = [
            ("kb_entry", uuid4(), "h1", [0.1, 0.2], "m1", 2),
            ("chapter", uuid4(), "h2", [0.3, 0.4, 0.5], "m2", 3),
        ]
        sql, _params = build_batch_upsert_query(items)
        bound = self._bound_keys(sql)
        assert {"p0_vec", "p1_vec"} <= bound
        rendered = str(sql.compile(dialect=postgresql.asyncpg.dialect()))
        assert rendered.count("CAST(") == 2
        assert "::vector" not in rendered

    def test_no_inline_vector_cast_in_embeddings_module(self) -> None:
        """Source-level guard: no ``:param::vector`` inline cast anywhere.

        Covers ``repository.upsert``'s inline SQL (not built by a
        ``search_queries`` function) so the invariant holds for all four
        vector-typed sites.
        """
        for mod in (repository_module, search_queries_module):
            source = inspect.getsource(mod)
            assert "::vector" not in source, (
                f"{mod.__name__} reintroduced an inline ``::vector`` cast — "
                "use ``CAST(:param AS vector)`` instead (see this test class)."
            )
