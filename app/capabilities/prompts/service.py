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

The preview (W8) renders a source at sample scope through the same sandbox
and answers the text beside the provenance and the diagnostics — no model
call, nothing persisted. The live test gates the editor draft through the
save gate, then hands the call to the key's own assembly (the registry's
``assemble`` slot — the capability's real context builder) and the key's
task cascade, after claiming the user's one live test per window.
"""

from dataclasses import dataclass
from time import monotonic
from typing import Final
from uuid import UUID  # noqa: TC003

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.capabilities.prompts.schemas import (
    PromptDetail,
    PromptDiff,
    PromptOverride,
    PromptPreview,
    PromptPreviewDiagnostics,
    PromptSummary,
    PromptVariable,
    PromptVariableProvenance,
)
from app.kernel.context import BudgetImpossibleError
from app.kernel.contracts.models import Novel
from app.kernel.embeddings.contract import EmbeddingProvider  # noqa: TC001  the live test's param
from app.kernel.llm.resolution import ResolvedProvider, resolve_provider
from app.kernel.prompts import (
    REASONS,
    LiveContextMissingError,
    LiveTestContext,
    PromptRenderError,
    PromptSpec,
    get_registry,
    referenced_names,
    render_source,
)
from app.kernel.prompts.models import PromptTemplate, PromptTemplateRepository

REFUSAL_REASONS: Final[tuple[str, ...]] = ("novel-scope", "unknown-novel", "contract")
"""The gate's own refusals, beside the render's vocabulary (``REASONS``)."""

LIVE_TEST_COOLDOWN_SECONDS: Final[float] = 30.0
"""The per-user live-test window: one test, then the wait.

The limit guards the provider's cost, not the reads: a request is claimed
only once its draft passed the gate and its real context assembled — a
refused or context-less test burns nothing — and the claim is what a later
immediate call is refused against.
"""

_LIVE_TEST_LAST: dict[UUID, float] = {}
"""The ledger of claims: each user's monotonic time of their last live test."""


class LiveTestRateLimitedError(RuntimeError):
    """The user's last live test is still inside the window.

    ``retry_after`` carries the remaining seconds, whole — the Retry-After
    header's number.
    """

    def __init__(self, retry_after: float) -> None:
        super().__init__(
            f"a live test just ran; the next one is allowed in {retry_after:.0f} seconds"
        )
        self.retry_after = max(1, round(retry_after))


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
        """A ``novel_id`` is only legal where the key carries the scope.

        Deliberate asymmetry (WP4 follow-up #392): ``detail`` and ``diff`` accept
        a ``novel_id`` for any key and fall back to the global tier when the key
        is not novel-scopable, so a page can render in a novel context; ``save``
        and ``delete`` refuse a novel scope for such a key, because there is no
        per-novel row to write or remove. No override leaks either way.
        """
        if novel_id is not None and not spec.novel_scopable:
            raise PromptRefusedError(
                "novel-scope",
                f"'{spec.key}' carries no novel scope; save it without a novel",
            )

    async def validate(self, key: str, content: str, novel_id: UUID | None) -> None:
        """The save-time gate: refuse by name, store nothing.

        Design note (WP4 follow-up #389): the gate resolves ``{% include %}``
        for this key to the content being saved and every other key to its
        bundled template, so an override that includes another key validates
        against that key's bundled (sample) variables. A hand-set template can
        include another key, and call-time render walks the full chain;
        chain-resolved validation at save time is deferred — the bundled target
        is the contract the gate checks.

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

    async def preview(self, key: str, novel_id: UUID | None, content: str | None) -> PromptPreview:
        """Render a source at sample scope through the save gate's sandbox.

        The scope's saved effective is the source when no draft is carried
        (the bundled template when neither exists); a carried draft renders
        as it stands. The include chain is the gate's own — the source under
        preview resolves its key's own includes, every other key to its
        bundled template — so what the editor sees is exactly what a save
        would validate. A render the sandbox refuses raises
        :class:`PromptRefusedError` the router answers with the named 422;
        a contract failure is a diagnostic (``contract_ok``), not a refusal —
        the preview's job is to show the draft beside what the save would
        say about it. No model call, nothing persisted, no write at all.
        """
        spec = self._spec(key)
        if novel_id is not None:
            await self._require_novel(novel_id)
        if content is None:
            row = await self._repository().effective(key, novel_id)
            source = row.content if row is not None else spec.template
        else:
            source = content

        def include(name: str) -> str:
            # The gate's chain at sample scope: the source under preview for
            # its own key, the bundled templates for every other.
            if name == key:
                return source
            return get_registry().spec(name).template  # unknown -> include-missing

        try:
            rendered = render_source(source, spec.sample_variables(), include=include)
        except PromptRenderError as error:
            raise PromptRefusedError(error.reason, error.detail) from None
        reads = referenced_names(source)
        return PromptPreview(
            rendered=rendered,
            variables=[
                PromptVariableProvenance(name=name, value=str(value), used=name in reads)
                for name, value in spec.sample_variables().items()
            ],
            diagnostics=PromptPreviewDiagnostics(
                chars=len(rendered),
                lines=rendered.count("\n") + 1,
                contract_ok=None if spec.contract is None else spec.contract(rendered),
            ),
        )

    async def prepare_live_test(
        self, key: str, content: str | None, novel_id: UUID | None, embeddings: EmbeddingProvider
    ) -> LiveTestPrepared:
        """Gate the draft, resolve the key's task, assemble the real context.

        The order is the promise: the save gate runs on a carried draft
        before anything else (a refusal is the 422, no window burned); the
        scope rules and the owned-novel read hold as on every route; the
        key's task cascade resolves (a key its tier can no longer produce
        raises :class:`app.kernel.secrets.KeyUnavailableError`, the router's
        503 face); the key's own assembly gathers the capability's real
        context and renders the draft-or-chain source against it — a render
        it refuses is the named 422 (:class:`PromptRefusedError`), a book
        with nothing to assemble :class:`LiveContextMissingError`, the router's
        409. Only then is the user's window claimed: a refused or
        context-less test consumed no provider, so it spends no wait.

        Nothing here writes: the draft never becomes an override, the
        assembly reads only, and the audit is the stream's own row.
        """
        spec = self._spec(key)
        self._refuse_scope(spec, novel_id)
        if novel_id is not None:
            await self._require_novel(novel_id)
        source: str | None
        if content is not None:
            await self.validate(key, content, novel_id)
            source, mode = content, "draft"
        else:
            row = await self._repository().effective(key, novel_id)
            source, mode = (row.content if row is not None else None), "effective"

        resolved = await resolve_provider(self.session, self.user_id, key)
        assemble = spec.assemble
        if assemble is None:
            # Every bundled key registers one; a key without its assembly is
            # a registration gap, not a user-facing refusal.
            raise RuntimeError(f"the bundled prompt '{key}' carries no live assembly")
        context = LiveTestContext(
            session=self.session,
            user_id=self.user_id,
            novel_id=novel_id,
            source=source,
            resolved=resolved,
            embeddings=embeddings,
        )
        try:
            assembled = await assemble(context)
        except LiveContextMissingError:
            raise
        except PromptRenderError as error:
            raise PromptRefusedError(error.reason, error.detail) from None
        except BudgetImpossibleError as error:
            raise PromptRefusedError("budget", str(error)) from None

        retry_after = _claim_live_test_slot(self.user_id)
        if retry_after > 0:
            raise LiveTestRateLimitedError(retry_after)
        return LiveTestPrepared(
            key=key,
            novel_id=novel_id,
            source_mode=mode,
            facts=assembled.facts,
            prompt=assembled.prompt,
            resolved=resolved,
        )


@dataclass(frozen=True)
class LiveTestPrepared:
    """The gated, assembled live test: everything the stream needs.

    ``prompt`` is the rendered source the provider answers; ``facts`` names
    what rode in (the context frame's payload); ``resolved`` is the tier the
    call rides and the audit names. ``source_mode`` says which source the
    prompt rendered — ``draft`` when the request carried one, ``effective``
    when the chain's pick served (an override, or the bundled template).
    """

    key: str
    novel_id: UUID | None
    source_mode: str
    facts: dict[str, str]
    prompt: str
    resolved: ResolvedProvider


def _claim_live_test_slot(user_id: UUID) -> float:
    """Claim the user's live-test window; the remaining wait, 0.0 when free.

    A refused claim moves nothing: the user's window stays where their last
    real claim put it, so the wait is honest rather than extended.
    """
    now = monotonic()
    last = _LIVE_TEST_LAST.get(user_id)
    if last is not None:
        elapsed = now - last
        if elapsed < LIVE_TEST_COOLDOWN_SECONDS:
            return LIVE_TEST_COOLDOWN_SECONDS - elapsed
    _LIVE_TEST_LAST[user_id] = now
    return 0.0


def _bundled_summary(spec: PromptSpec) -> str:
    """The bundled prompt rendered at sample scope, cut for the list row."""
    return render_source(spec.template, spec.sample_variables(), include=_bundled_include)[:120]
