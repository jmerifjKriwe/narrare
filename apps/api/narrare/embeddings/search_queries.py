"""Embedding search query builders for pgvector.

Extracts raw SQL query construction from the repository for RULE-04
compliance. No business logic — only SQL string building and parameter
assembly for vector operations.

RULE-06: One responsibility — query builders only, no DB execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy
from sqlalchemy import TextClause

from narrare.embeddings.models import Embedding

if TYPE_CHECKING:
    from uuid import UUID


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


def build_search_query(
    query_vec_str: str,
    *,
    source_type: str | None = None,
    source_ids: set[UUID] | None = None,
    threshold: float = 0.7,
    limit: int = 20,
    model: str | None = None,
) -> tuple[TextClause, dict[str, object]]:
    """Build the vector similarity search SQL and parameters.

    Constructs a ``SELECT`` with cosine distance filtering via
    ``<=>`` operator. Returns ``(sql_text, params_dict)``.
    """
    conditions = ["1 - (embedding <=> :query_vec::vector) >= :threshold"]
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

    where_clause = " AND ".join(conditions)

    sql = sqlalchemy.text(
        "SELECT id, source_type, source_id, content_hash, "  # nosec B608
        "embedding, model, dimension, generated_at, "
        "1 - (embedding <=> :query_vec::vector) AS similarity "
        "FROM embeddings "
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
            + "ch, :"
            + prefix
            + "vec::vector, :"
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
