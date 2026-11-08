from app.kernel.contracts import models
from app.kernel.db.base import Base


def test_the_aggregator_registers_every_shared_table() -> None:
    expected = {
        "users",
        "novels",
        "chapters",
        "entities",
        "entity_relations",
        "entity_suggestions",
        "consistency_findings",
        "documents",
        "chunks",
    }
    assert expected <= set(Base.metadata.tables)
    assert models.Novel.__tablename__ == "novels"
    assert models.Document.__tablename__ == "documents"
