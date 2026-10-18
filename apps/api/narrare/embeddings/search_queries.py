"""Embedding search query builders for pgvector.

Extracts raw SQL query construction from the repository for RULE-04
compliance. No business logic — only SQL string building and parameter
assembly for vector operations.

RULE-06: One responsibility — query builders only, no DB execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, cast

import sqlalchemy
from sqlalchemy import TextClause

from narrare.embeddings.contracts import (
    DEFAULT_EMBEDDING_SEARCH_LIMIT,
    DEFAULT_EMBEDDING_SEARCH_THRESHOLD,
)
from narrare.embeddings.models import Embedding

if TYPE_CHECKING:
    from uuid import UUID


# ---------------------------------------------------------------------------
# Search result row — carries embedding + KB entry metadata
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SearchRow:
    """Enriched result from embedding vector search.

    Combines the embedding row with similarity score and KB entry metadata
    (usage tracking) needed for hybrid scoring.

    Attributes:
        embedding: The matched Embedding ORM object.
        similarity: Cosine similarity score in [0.0, 1.0].
        usage_count: Number of times the KB entry was referenced.
            0 for non-kb_entry sources or unreferenced entries.
        last_referenced_at: Timestamp of last reference, or None.
    """

    embedding: Embedding
    similarity: float
    usage_count: int
    last_referenced_at: datetime | None


def build_vector_str(embedding: list[float]) -> str:
    """Convert a float list to pgvector string format ``[1.0,2.0,...]``."""
    return "[" + ",".join(str(v) for v in embedding) + "]"


def parse_embedding_row(row: tuple[object, ...]) -> Embedding:
    """Convert a raw SQL result row to an Embedding model.

    Expects row columns in order:
    ``(id, source_type, source_id, content_hash, embedding, model,
    dimension, generated_at)``
    """
    return Embedding(
        id=row[0],
        source_type=row[1],
        source_id=row[2],
        content_hash=row[3],
        embedding=row[4],
        model=row[5],
        dimension=row[6],
        generated_at=row[7],
    )


def parse_search_row(row: tuple[object, ...]) -> SearchRow:
    """Convert a search result row to a SearchRow.

    Expects row columns in order:
    ``(id, source_type, source_id, content_hash, embedding, model,
    dimension, generated_at, similarity, usage_count, last_referenced_at)``
    """
    embedding = Embedding(
        id=row[0],
        source_type=row[1],
        source_id=row[2],
        content_hash=row[3],
        embedding=row[4],
        model=row[5],
        dimension=row[6],
        generated_at=row[7],
    )
    similarity_value = cast("float | None", row[8])
    usage_value = cast("int | None", row[9])
    referenced_at = cast("datetime | None", row[10])

    return SearchRow(
        embedding=embedding,
        similarity=float(similarity_value) if similarity_value is not None else 0.0,
        usage_count=int(usage_value) if usage_value is not None else 0,
        last_referenced_at=referenced_at if isinstance(referenced_at, datetime) else None,
    )


def build_search_query(
    query_vec_str: str,
    *,
    source_type: str | None = None,
    source_ids: set[UUID] | None = None,
    threshold: float = DEFAULT_EMBEDDING_SEARCH_THRESHOLD,
    limit: int = DEFAULT_EMBEDDING_SEARCH_LIMIT,
    model: str | None = None,
    novel_id: UUID | None = None,
) -> tuple[TextClause, dict[str, object]]:
    """Build the vector similarity search SQL and parameters.

    Constructs a ``SELECT`` with cosine distance filtering via
    ``<=>`` operator. Returns ``(sql_text, params_dict)``.

    ``novel_id`` scopes the search to one novel's KB entries (ADR-088
    anti-enumeration: suggestions must never surface another novel's
    entries, and orphaned embedding rows — whose source entry is gone —
    can never match either, because the KB join is required when the
    scope is set). NaN distances are excluded unconditionally: a
    zero-vector stored embedding makes ``<=>`` return NaN, and Postgres
    orders NaN **above** every real number — without the guard such rows
    pass the threshold with a NaN similarity and poison the response.
    """
    distance = "embedding <=> CAST(:query_vec AS vector)"
    conditions = [
        f"1 - ({distance}) >= :threshold",
        # NaN = NaN is TRUE in Postgres (unlike IEEE 754), so this filters
        # exactly the zero-vector rows. CAST form — the ``'NaN'::real``
        # literal would trip the ``:name::TYPE`` asyncpg bind-param bug
        # (see TestVectorParamsAreBoundByDialect).
        f"({distance}) <> CAST('NaN' AS real)",
    ]
    params: dict[str, object] = {
        "query_vec": query_vec_str,
        "threshold": threshold,
        "limit": limit,
    }

    if source_type is not None:
        conditions.append("source_type = :source_type")
        params["source_type"] = source_type

    if model is not None:
        conditions.append("model = :model")
        params["model"] = model

    if source_ids is not None and source_ids:
        id_strs = [str(sid) for sid in source_ids]
        conditions.append("source_id = ANY(:source_ids)")
        params["source_ids"] = id_strs

    if novel_id is not None:
        # Requires the kb_entries join to match — orphaned embedding rows
        # (source entry deleted) and other source_types are excluded.
        conditions.append("kb.novel_id = :novel_id")
        params["novel_id"] = str(novel_id)

    where_clause = " AND ".join(conditions)

    sql = sqlalchemy.text(
        "SELECT e.id, e.source_type, e.source_id, e.content_hash, "  # nosec B608
        "e.embedding, e.model, e.dimension, e.generated_at, "
        "1 - (e.embedding <=> CAST(:query_vec AS vector)) AS similarity, "
        "COALESCE(kb.usage_count, 0) AS usage_count, "
        "kb.last_referenced_at "
        "FROM embeddings e "
        "LEFT JOIN kb_entries kb ON e.source_id = kb.id AND e.source_type = 'kb_entry' "
        "WHERE " + where_clause + " "
        "ORDER BY similarity DESC "
        "LIMIT :limit"
    )
    return sql, params


def build_get_by_source_query(
    source_type: str,
    source_id: UUID,
    model: str | None = None,
) -> tuple[TextClause, dict[str, object]]:
    """Build the get_by_source SELECT SQL and parameters."""
    conditions = ["source_type = :source_type", "source_id = :source_id"]
    params: dict[str, object] = {
        "source_type": source_type,
        "source_id": str(source_id),
    }

    if model is not None:
        conditions.append("model = :model")
        params["model"] = model

    where_clause = " AND ".join(conditions)

    sql = sqlalchemy.text(
        "SELECT id, source_type, source_id, content_hash, "  # nosec B608
        "embedding, model, dimension, generated_at "
        "FROM embeddings "
        "WHERE " + where_clause
    )
    return sql, params


def build_batch_upsert_query(
    items: list[tuple[str, UUID, str, list[float], str, int]],
) -> tuple[TextClause, dict[str, object]]:
    """Build the batch INSERT ON CONFLICT SQL and parameters.

    Each item is a tuple:
    ``(source_type, source_id, content_hash, embedding, model, dimension)``
    """
    values_clauses: list[str] = []
    params: dict[str, object] = {}

    for i, (s_type, s_id, c_hash, emb, mdl, dim) in enumerate(items):
        vec_str = build_vector_str(emb)
        prefix = f"p{i}_"
        values_clauses.append(
            "(gen_random_uuid(), :"
            + prefix
            + "st, :"
            + prefix
            + "sid, :"
            + prefix
            + "ch, CAST(:"
            + prefix
            + "vec AS vector), :"
            + prefix
            + "mdl, :"
            + prefix
            + "dim, now())"
        )
        params[prefix + "st"] = s_type
        params[prefix + "sid"] = str(s_id)
        params[prefix + "ch"] = c_hash
        params[prefix + "vec"] = vec_str
        params[prefix + "mdl"] = mdl
        params[prefix + "dim"] = dim

    values_sql = ", ".join(values_clauses)

    sql = sqlalchemy.text(
        "INSERT INTO embeddings "  # nosec B608
        "(id, source_type, source_id, content_hash, "
        "embedding, model, dimension, generated_at) "
        "VALUES " + values_sql + " "  # nosec B608
        "ON CONFLICT (source_type, source_id, model) "
        "DO UPDATE SET "
        "content_hash = EXCLUDED.content_hash, "
        "embedding = EXCLUDED.embedding, "
        "dimension = EXCLUDED.dimension, "
        "generated_at = now()"
    )
    return sql, params
