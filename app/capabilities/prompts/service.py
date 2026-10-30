"""Reading and writing prompt overrides, and the save-time gate.

The key set is closed — the registry's bundled prompts are what a user may
re-voice — so an unknown key is a 404 and every write validates first. The
gate renders the saved source through the same sandboxed renderer the real
call uses, at sample scope (the sample variables every bundled prompt
registers), and refuses by name: the render's own reason, the key's
contract, the scope rules. A refusal stores nothing; an accepted save lands
through the repository's atomic upsert, so a double submit or a true race
is one saved row, never a 500.

Every ``novel_id`` is checked against the user's own novels before it
reaches a write: an id that names another user's novel is a named 422,
never a trusted foreign key.
"""

from typing import Final
from uuid import UUID  # noqa: TC003

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.capabilities.prompts.schemas import (
    PromptDetail,
    PromptDiff,
    PromptOverride,
    PromptSummary,
    PromptVariable,
)
from app.kernel.contracts.models import Novel
from app.kernel.prompts import (
    REASONS,
    PromptRenderError,
    PromptSpec,
    get_registry,
    render_source,
)
from app.kernel.prompts.models import PromptTemplate, PromptTemplateRepository

REFUSAL_REASONS: Final[tuple[str, ...]] = ("novel-scope", "unknown-novel", "contract")
"""The gate's own refusals, beside the render's vocabulary (``REASONS``)."""


class PromptNotFoundError(LookupError):
    """No bundled prompt carries the key."""


class PromptRefusedError(ValueError):
    """The save-time gate refuses; ``reason`` names which refusal, the message says more.

    ``reason`` is one of :data:`REFUSAL_REASONS` or the render's own
    vocabulary (:data:`REASONS`) — a reason outside the union is a
    programming error and raises before any 422 can carry it.
    """

    def __init__(self, reason: str, detail: str) -> None:
        if reason not in REFUSAL_REASONS and reason not in REASONS:
            raise ValueError(
                f"'{reason}' is outside the refusal vocabulary {REFUSAL_REASONS + REASONS}"
            )
        self.reason = reason
        super().__init__(detail)


def _bundled_include(name: str) -> str:
    """The include chain of a purely bundled render: bundled resolves bundled."""
    return get_registry().spec(name).template  # unknown -> include-missing


def _override_of(row: PromptTemplate | None) -> PromptOverride | None:
    """The row as a read shows it: which tier answered, and its content."""
    if row is None:
        return None
    return PromptOverride(
        scope="novel" if row.novel_id is not None else "global", content=row.content
    )


class PromptService:
    """The overrides over the registry; the commit is always here."""

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id

    def _repository(self) -> PromptTemplateRepository:
        return PromptTemplateRepository(self.session, self.user_id)

    def _spec(self, key: str) -> PromptSpec:
        """The bundled spec for the key; an unknown key is the 404."""
        try:
            return get_registry().spec(key)
        except KeyError:
            raise PromptNotFoundError(f"unknown prompt key: '{key}'") from None

    async def _require_novel(self, novel_id: UUID) -> None:
        """The authorized read behind every ``novel_id``: the user's own novel.

        A foreign or invented id is refused by name — the scope's write is
        never allowed to ride on an id nobody authorized.
        """
        owned = await self.session.scalar(
            select(Novel.id).where(Novel.id == novel_id, Novel.user_id == self.user_id)
        )
        if owned is None:
            raise PromptRefusedError(
                "unknown-novel",
                f"no novel '{novel_id}' of yours; an override's novel must be one of yours",
            )

    def _refuse_scope(self, spec: PromptSpec, novel_id: UUID | None) -> None:
        """A ``novel_id`` is only legal where the key carries the scope."""
        if novel_id is not None and not spec.novel_scopable:
            raise PromptRefusedError(
                "novel-scope",
                f"'{spec.key}' carries no novel scope; save it without a novel",
            )

    async def validate(self, key: str, content: str, novel_id: UUID | None) -> None:
        """The save-time gate: refuse by name, store nothing.

        The unknown key is the 404; ``novel_id`` is checked for scope and
        ownership; the content renders through the sandbox at sample scope —
        includes resolving to the saved content for this key, to the bundled
        templates for the others — and the key's contract runs over the
        render. Every refusal is a :class:`PromptRefusedError` the router
        answers with a 422 naming the reason.
        """
        spec = self._spec(key)
        self._refuse_scope(spec, novel_id)
        if novel_id is not None:
            await self._require_novel(novel_id)

        def include(name: str) -> str:
            # The chain at sample scope: this key's chain resolves to the
            # content being saved, every other key to its bundled template.
            if name == key:
                return content
            return get_registry().spec(name).template  # unknown -> include-missing

        try:
            rendered = render_source(content, spec.sample_variables(), include=include)
        except PromptRenderError as error:
            raise PromptRefusedError(error.reason, error.detail) from None
        if spec.contract is not None and not spec.contract(rendered):
            raise PromptRefusedError(
                "contract",
                f"the rendered prompt fails the contract of '{key}': "
                "the frame the caller depends on did not survive the re-voice",
            )

    async def list(self, novel_id: UUID | None) -> list[PromptSummary]:
        """Every bundled key with its facts and its two override tiers."""
        if novel_id is not None:
            await self._require_novel(novel_id)
        registry = get_registry()
        registered = registry.keys()
        repository = self._repository()
        summaries: list[PromptSummary] = []
        for key in registered:
            spec = registry.spec(key)
            global_row = await repository.effective(key, None)
            novel_row = await repository.effective(key, novel_id) if novel_id is not None else None
            summaries.append(
                PromptSummary(
                    key=key,
                    novel_scopable=spec.novel_scopable,
                    override_global=global_row is not None,
                    override_novel=novel_row is not None and novel_row.novel_id is not None,
                    bundled_summary=_bundled_summary(spec),
                )
            )
        return summaries

    async def detail(self, key: str, novel_id: UUID | None) -> PromptDetail:
        """One key as the editor shows it: the bundled source, the legend,
        the override in force, the source a render would use."""
        spec = self._spec(key)
        if novel_id is not None:
            await self._require_novel(novel_id)
        row = await self._repository().effective(key, novel_id)
        return PromptDetail(
            bundled_content=spec.template,
            variables=[
                PromptVariable(name=name, example=str(value))
                for name, value in spec.sample_variables().items()
            ],
            override=_override_of(row),
            effective_content=row.content if row is not None else spec.template,
        )

    async def diff(self, key: str, novel_id: UUID | None) -> PromptDiff:
        """The bundled template against the override in force for the scope."""
        spec = self._spec(key)
        if novel_id is not None:
            await self._require_novel(novel_id)
        row = await self._repository().effective(key, novel_id)
        return PromptDiff(
            bundled_content=spec.template,
            override_content=row.content if row is not None else None,
        )

    async def save(self, key: str, content: str, novel_id: UUID | None) -> PromptDetail:
        """Validate, then upsert the scope's row; the fresh detail answers.

        The gate runs first — a refusal stores nothing. The accepted write
        lands through the repository's single-statement upsert, so two
        concurrent saves on an empty scope serialize at the database and the
        loser becomes the update, never an ``IntegrityError``; the commit is
        here, inside the request's own transaction.
        """
        await self.validate(key, content, novel_id)
        await self._repository().save(key, content, novel_id)
        await self.session.commit()
        return await self.detail(key, novel_id)

    async def delete(self, key: str, novel_id: UUID | None) -> None:
        """Remove the override for the scope; a scope with no row stays a 204.

        The key and the scope rules are checked like every write: an unknown
        key is the 404, a foreign or impossible ``novel_id`` the named 422 —
        the reset never acts on an id nobody authorized. The other tier is
        untouched.
        """
        spec = self._spec(key)
        self._refuse_scope(spec, novel_id)
        if novel_id is not None:
            await self._require_novel(novel_id)
        await self._repository().delete(key, novel_id)
        await self.session.commit()


def _bundled_summary(spec: PromptSpec) -> str:
    """The bundled prompt rendered at sample scope, cut for the list row."""
    return render_source(spec.template, spec.sample_variables(), include=_bundled_include)[:120]
