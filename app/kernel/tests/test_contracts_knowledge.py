"""The shared relation bound: one kernel constant, two capabilities refusing it.

Rule 1 keeps chat and knowledge from importing each other, so a bound both
enforce lives in the kernel and both import it. These tests pin that sharing
and the refusal point itself: thirteen lines are one over the bound on either
path — the create endpoint raises, the interview's normalisation drops the
thirteenth. The imports below point at capabilities from a kernel test on
purpose: this is the one place that proves both consumers bind the kernel
constant, and test-only imports never become the production direction.
"""

from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest

from app.capabilities.chat import interviews
from app.capabilities.knowledge import service as knowledge_service
from app.capabilities.knowledge.schemas import EntityCreate, RelationLine
from app.capabilities.knowledge.service import KnowledgeService, RelationLimitError
from app.kernel.auth import LOCAL_USER_ID
from app.kernel.contracts.knowledge import MAX_RELATIONS
from app.kernel.contracts.models import Novel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.kernel.embeddings import EmbeddingProvider


def test_the_bound_is_twelve() -> None:
    assert MAX_RELATIONS == 12


def test_both_services_read_the_kernel_constant() -> None:
    """A literal copied back into either service fails here, not in review."""
    assert knowledge_service.MAX_RELATIONS is MAX_RELATIONS
    assert interviews.MAX_RELATIONS is MAX_RELATIONS


async def test_the_create_path_refuses_the_thirteenth_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The create endpoint raises at ``MAX_RELATIONS`` lines, before the
    first write. The ownership read is stubbed: the count guard runs before
    any session use, and who owns the novel is not this pin's subject."""
    novel_id = uuid4()

    async def owned(self: KnowledgeService, asked: UUID) -> Novel:
        return Novel(id=asked, user_id=self.user_id, title="Die Nevada-Anlage")

    monkeypatch.setattr(KnowledgeService, "_own_novel", owned)
    # The repositories only store their session; the guard raises before any
    # query, so no database is needed for this pin.
    service = KnowledgeService(
        cast("AsyncSession", object()), LOCAL_USER_ID, cast("EmbeddingProvider", object())
    )
    payload = EntityCreate(
        novel_id=novel_id,
        name="Nevada-Trümmerfeld",
        type="location",
        relations=[
            RelationLine(to_entity_id=uuid4(), relation_type=f"verweist_{index}")
            for index in range(MAX_RELATIONS + 1)
        ],
    )

    with pytest.raises(RelationLimitError) as refused:
        await service.create_entity(payload)

    assert refused.value.row == MAX_RELATIONS
    assert str(MAX_RELATIONS) in str(refused.value)


def test_the_interview_normalisation_keeps_twelve() -> None:
    """The thirteenth proposed relation is the one the answer loses."""
    answered = [
        {"target": f"Target {index}", "type": "knows", "note": ""}
        for index in range(MAX_RELATIONS + 1)
    ]

    kept = interviews._normalise_relations(  # pyright: ignore[reportPrivateUsage]  the pure normalisation is the unit under test
        answered
    )

    assert len(kept) == MAX_RELATIONS
    assert kept[-1]["target"] == f"Target {MAX_RELATIONS - 1}"
