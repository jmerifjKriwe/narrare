"""The model service: the invariants, the gate, the probe.

A model belongs to a provider: the row names its provider and the model
string, and everything endpoint-shaped — kind, base URL, key, mask — lives
on the provider it points at (design D7 and the settings surface). What a
model owns is its identity and its tuning: exactly one default per user with
the flip in one transaction, the delete guard that names the way out, and
the write gate that refuses a model whose ``provider_id`` does not name one
of the user's own providers — a cross-user pointer must be refused, never
silently linked. The probe runs against the model's provider's endpoint: one
cheap completion audited as ``settings.test``, asking for the model string
the row carries.

No side effect beyond the request's own transaction: each method commits
once, and the test probe's audit row rides the audit finalizer's own short
session the way every audited stream's does.
"""

from collections.abc import Sequence  # noqa: TC003
from dataclasses import dataclass
from datetime import datetime  # noqa: TC003  the state's field annotation
from time import monotonic
from typing import TYPE_CHECKING, Literal
from uuid import UUID  # noqa: TC003  the service's parameter annotations name it

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.llm.audit import audited_stream
from app.kernel.llm.catalog import ModelInfo, effective_info
from app.kernel.llm.contract import CompletionRequest
from app.kernel.llm.models import (
    CUSTOM_OUTPUT_PROFILE,
    ERROR,
    LlmCall,
    LLMProvider,
    ProviderProfile,
    TaskAssignment,
)
from app.kernel.llm.repositories import AssignmentRepository, ProfileRepository, ProviderRepository
from app.kernel.llm.resolution import (
    AUDIT_ONLY_TASK_KEYS,
    KNOWN_TASK_KEYS,
    OutputProfile,
    from_profile,
    resolve_provider,
)

if TYPE_CHECKING:
    from app.capabilities.settings.schemas import ModelCreate, ModelUpdate

PROBE_PROMPT = "Reply with a single word: ok."
"""The one cheap completion a connection test asks for."""


class ProfileNotFoundError(LookupError):
    """No profile of the user's carries the id."""


class ProfileRefusedError(ValueError):
    """The gate refuses this create or update; ``fields`` names the columns."""

    def __init__(self, fields: tuple[str, ...], message: str) -> None:
        super().__init__(message)
        self.fields = fields


class DefaultProfileError(RuntimeError):
    """The default model cannot be deleted; the message names the way out."""


class DefaultProfileRaceError(RuntimeError):
    """Another create or default swap made its model the default first.

    The create race and the two-swap race both land here; only one default may
    exist.
    """


@dataclass(frozen=True)
class TestResult:
    """What one connection test found: it ran, and it either answered or named why."""

    ok: bool
    error: str | None
    latency_ms: int


@dataclass(frozen=True)
class ModelState:
    """What the settings row's marks say about one model, beyond its columns.

    ``in_catalog`` is the resolution-side lookup's own answer — the same
    :func:`app.kernel.llm.catalog.effective_info` tiers a generation prices
    with — so the page never derives a second truth about what the catalog
    carries. ``catalog_max_output_tokens`` is that lookup's own output
    ceiling for the model string, read-only: the assignment gate bounds a
    custom choice by the model's stored ``max_output_tokens`` alone (the
    catalog prices the call and is no ceiling, W8 ruling 5), so the
    Aufgaben editor needs this answer beside it to name — and refuse
    above — the one limit the provider is known to enforce. ``last_error_code``
    and ``last_error_at`` are the model's newest audit row's, present only
    when that call failed: a later success clears the mark, because the
    mark speaks about the *last* call, not the worst.
    """

    in_catalog: bool
    catalog_max_output_tokens: int | None
    last_error_code: str | None
    last_error_at: datetime | None


@dataclass(frozen=True)
class TaskEffective:
    """One known task key and the provider the cascade actually serves it.

    ``output_profile`` and ``resolved_output_tokens`` carry the task's
    output choice (W8): the serving assignment's profile and the number a
    call reserves — the profile's target, capped by the assigned model's
    stored ceiling where one is stored. ``None`` where no profile applies:
    the audit-only key routes to no model and reserves nothing.
    """

    task_key: str
    profile_id: UUID | None
    profile_name: str | None
    kind: str
    assignable: bool
    output_profile: str | None
    resolved_output_tokens: int | None


class ModelService:
    """The model invariants over the repositories; the commit is always here."""

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.session = session
        self.user_id = user_id

    def _profiles(self) -> ProfileRepository:
        return ProfileRepository(self.session, self.user_id)

    def _providers(self) -> ProviderRepository:
        return ProviderRepository(self.session, self.user_id)

    def _assignments(self) -> AssignmentRepository:
        return AssignmentRepository(self.session, self.user_id)

    async def list(self) -> Sequence[tuple[ProviderProfile, LLMProvider]]:
        """Every model of the user's with its provider: the default first.

        The provider comes back beside the model because every read names it;
        the NOT NULL pointer and the FK keep the pair complete for every row
        the writers store. A row whose provider is gone anyway — reachable
        only by repair SQL, never through the writers — is skipped, the way
        :meth:`_paired` refuses by name: the list stays readable instead of
        crashing on a dangling pointer it cannot fix.
        """
        names = {provider.id: provider for provider in await self._providers().ordered()}
        pairs: list[tuple[ProviderProfile, LLMProvider]] = []
        for profile in await self._profiles().ordered():
            provider = names.get(profile.provider_id)
            if provider is not None:
                pairs.append((profile, provider))
        return pairs

    async def create(self, payload: ModelCreate) -> tuple[ProviderProfile, LLMProvider]:
        """Store one model under one of the user's providers; the first is the default.

        The provider's own gate has already vetted the endpoint this model
        points at; the model gate refuses only what the model itself could
        get wrong — a provider that is not the user's, and an output
        reservation that leaves no input room.

        The default race is the profile create's (design D7): two creates
        that both read an empty table collide on the partial unique index,
        the loser rolls back and raises :class:`DefaultProfileRaceError` for
        the router's 409.
        """
        provider = await self._provider_of(payload.provider_id)
        self._gate(
            provider=provider,
            context_window=payload.context_window,
            max_output_tokens=payload.max_output_tokens,
        )
        profiles = self._profiles()
        # Before the flush: the first model is what makes the new one the
        # default, and after the flush it would already be listed.
        is_default = not await profiles.ordered()
        fields: dict[str, object] = {
            "name": payload.name,
            "provider_id": provider.id,
            "model": payload.model,
            "context_window": payload.context_window,
            "max_output_tokens": payload.max_output_tokens,
            "temperature": payload.temperature,
            "request_timeout": payload.request_timeout,
        }
        if is_default:
            try:
                profile = await profiles.create(**fields, is_default=True)
            except IntegrityError:
                await self.session.rollback()
                raise DefaultProfileRaceError(
                    "another create made its model the default at the same"
                    " moment; only one default can exist — reload and retry"
                ) from None
        else:
            profile = await profiles.create(**fields)
        await self.session.commit()
        return profile, provider

    async def update(
        self, model_id: UUID, payload: ModelUpdate
    ) -> tuple[ProviderProfile, LLMProvider]:
        """Apply the patch; the model string and the provider can both move.

        Clearing the name, the provider or the model string is refused —
        a model without one of them is not a configuration, and an absent
        field means "keep" the way it always did. The gate runs on the
        patched pair before anything is stored. ``is_default: true`` hands
        the default over from its holder in the same transaction; ``false``
        is refused — "models exist with no default" is not a legal state.
        Two swaps in flight can both unset the old holder before either
        raises its own model, so the later ``is_default = true`` flush trips
        the partial unique index; that one flush is caught and named
        :class:`DefaultProfileRaceError` (the create race's answer), never
        left as a bare ``IntegrityError``.
        """
        profiles = self._profiles()
        profile = await profiles.get(model_id)
        if profile is None:
            raise ProfileNotFoundError(f"no profile {model_id}")
        set_fields = payload.model_fields_set
        for field in ("name", "provider_id", "model"):
            if field in set_fields and getattr(payload, field) is None:
                raise ProfileRefusedError((field,), f"a model's {field} cannot be cleared")

        provider = (
            await self._provider_of(payload.provider_id)
            if "provider_id" in set_fields and payload.provider_id is not None
            else await self._paired(profile)
        )
        context_window = (
            payload.context_window if "context_window" in set_fields else profile.context_window
        )
        max_output_tokens = (
            payload.max_output_tokens
            if "max_output_tokens" in set_fields
            else profile.max_output_tokens
        )
        self._gate(
            provider=provider,
            context_window=context_window,
            max_output_tokens=max_output_tokens,
        )
        if payload.is_default is False:
            raise ProfileRefusedError(
                ("is_default",),
                "a model cannot stop being the default by patching;"
                " make another model the default first",
            )

        updates: dict[str, object] = {}
        for field in (
            "name",
            "provider_id",
            "model",
            "context_window",
            "max_output_tokens",
            "temperature",
            "request_timeout",
        ):
            if field in set_fields:
                updates[field] = getattr(payload, field)
        if updates:
            await profiles.update(profile, **updates)
        if payload.is_default:
            try:
                await self._unset_other_defaults(profile)
                await profiles.update(profile, is_default=True)
            except IntegrityError:
                await self.session.rollback()
                raise DefaultProfileRaceError(
                    "another swap made its model the default at the same"
                    " moment; only one default can exist — reload and retry"
                ) from None
        await self.session.commit()
        return profile, provider

    async def delete(self, model_id: UUID) -> None:
        """Remove a non-default model; its assignments cascade at the database.

        The default model is refused — including while it is the only one —
        with the error naming the way out (design D7).
        """
        profiles = self._profiles()
        profile = await profiles.get(model_id)
        if profile is None:
            raise ProfileNotFoundError(f"no profile {model_id}")
        if profile.is_default:
            raise DefaultProfileError(
                "the default model cannot be deleted; create a second model,"
                " make it the default, then delete this one"
            )
        await profiles.delete(profile)
        await self.session.commit()

    async def set_default(self, model_id: UUID) -> None:
        """Make this model the default, unsetting the holder in one transaction.

        The flip has the same lost-update window as :meth:`update`; the
        colliding ``is_default = true`` flush is the named race, never a bare
        ``IntegrityError``.
        """
        profiles = self._profiles()
        profile = await profiles.get(model_id)
        if profile is None:
            raise ProfileNotFoundError(f"no profile {model_id}")
        try:
            await self._unset_other_defaults(profile)
            await profiles.update(profile, is_default=True)
        except IntegrityError:
            await self.session.rollback()
            raise DefaultProfileRaceError(
                "another swap made its model the default at the same"
                " moment; only one default can exist — reload and retry"
            ) from None
        await self.session.commit()

    async def test(self, model_id: UUID) -> TestResult:
        """One cheap completion through the model's provider, audited as settings.test.

        The outcome is data, not a status: a dead endpoint, a refused key or
        a key its tier can no longer produce is a failed test that names why
        — one ``LlmCall`` row per provider call is the audit's identity, so
        the probe's call lands there however it ends.
        """
        profile = await self._profiles().get(model_id)
        if profile is None:
            raise ProfileNotFoundError(f"no profile {model_id}")
        provider = await self._paired(profile)
        started = monotonic()
        try:
            resolved = from_profile(profile, provider)
            async for _ in audited_stream(
                resolved,
                CompletionRequest.user(PROBE_PROMPT),
                user_id=self.user_id,
                task_key="settings.test",
            ):
                pass
        except Exception as failure:
            return TestResult(
                ok=False, error=str(failure), latency_ms=round((monotonic() - started) * 1000)
            )
        return TestResult(ok=True, error=None, latency_ms=round((monotonic() - started) * 1000))

    async def state(self, profile: ProviderProfile, provider: LLMProvider) -> ModelState:
        """One model's marks: whether the catalog prices it, and its last failure.

        The single-read shape of :meth:`states` — a create or update answers
        with the same fields the list shows, so no read ever carries a
        half-filled row.
        """
        last_error_code, last_error_at = await self._last_failure(profile.id)
        info = self._catalog_info(profile, provider)
        return ModelState(
            in_catalog=info is not None,
            catalog_max_output_tokens=info.max_output_tokens if info is not None else None,
            last_error_code=last_error_code,
            last_error_at=last_error_at,
        )

    async def states(
        self, pairs: Sequence[tuple[ProviderProfile, LLMProvider]]
    ) -> dict[UUID, ModelState]:
        """Every listed model's marks, for the settings page's three marks.

        The list is small, so the failure read is one newest-first query per
        model instead of a window-function join — the same answer, at a
        shape the catalog lookup can ride beside. Reads only: neither the
        catalog tier nor the audit query writes, and the page's marks are
        never stored anywhere.
        """
        states: dict[UUID, ModelState] = {}
        for profile, provider in pairs:
            last_error_code, last_error_at = await self._last_failure(profile.id)
            info = self._catalog_info(profile, provider)
            states[profile.id] = ModelState(
                in_catalog=info is not None,
                catalog_max_output_tokens=info.max_output_tokens if info is not None else None,
                last_error_code=last_error_code,
                last_error_at=last_error_at,
            )
        return states

    async def assignments(self) -> Sequence[TaskAssignment]:
        """Every assignment of the user's, ordered by task key."""
        return await self._assignments().list_all()

    async def tasks(self) -> Sequence[TaskEffective]:
        """One row per known task key, naming the provider that serves it.

        Each routable key is resolved on this request's read-only session,
        through the same cascade a generation uses, so the answer is what the
        next call will get: the exact assignment, a sibling's segment
        assignment, the default model, or the environment tier.
        ``profile_name`` is ``None`` exactly when no model serves. The row's
        ``resolved_output_tokens`` is the same number the next call reserves
        — one truth, never a second derivation. Audit-only keys
        (:data:`AUDIT_ONLY_TASK_KEYS`) are never routed — the settings probe
        audits its call under ``settings.test`` but tests the clicked model —
        so they report ``kind="audit"`` and are not assignable, without
        consulting the cascade. Resolution never writes, so reading the list
        creates no assignment and audits no call.
        """
        names = {profile.id: profile.name for profile, _ in await self.list()}
        rows: list[TaskEffective] = []
        for task_key in KNOWN_TASK_KEYS:
            if task_key in AUDIT_ONLY_TASK_KEYS:
                rows.append(
                    TaskEffective(
                        task_key=task_key,
                        profile_id=None,
                        profile_name=None,
                        kind="audit",
                        assignable=False,
                        output_profile=None,
                        resolved_output_tokens=None,
                    )
                )
                continue
            resolved = await resolve_provider(self.session, self.user_id, task_key)
            rows.append(
                TaskEffective(
                    task_key=task_key,
                    profile_id=resolved.profile_id,
                    profile_name=names.get(resolved.profile_id) if resolved.profile_id else None,
                    kind=resolved.kind,
                    assignable=True,
                    output_profile=resolved.output_profile,
                    resolved_output_tokens=resolved.resolved_output_tokens,
                )
            )
        return rows

    async def driver(self) -> Literal["fake", "configured"]:
        """The instance's driver kind: the tasks read's own answer, reduced.

        ``"fake"`` while every assignable task's serving tier is the fake
        adapter — the cascade's floor or a stored fake row — else
        ``"configured"``. The reduction runs over :meth:`tasks`, the one
        resolution path: no second cascade exists to drift from it, and a
        provider whose key its tier can no longer produce fails here as it
        fails there, before the word is spoken. Audit-only keys name no
        driver and are skipped, as there.
        """
        kinds = {row.kind for row in await self.tasks() if row.assignable}
        return "fake" if kinds <= {"fake"} else "configured"

    async def assign(
        self,
        task_key: str,
        profile_id: UUID | None,
        output_profile: OutputProfile | None = None,
    ) -> TaskAssignment | None:
        """Point the task at one of the user's models, or clear it with ``None``.

        Any non-empty task key is accepted — the known keys are a kernel
        constant for readers, not a format; a new capability's key can be
        assigned before its list entry ships.

        The output profile rides the assignment (W8). A choice the caller did
        not carry is the vocabulary's default — absent and null both mean
        ``balanced``, no two-state semantics. A custom choice is bounded to a
        known ceiling at save: a number above the assigned model's stored
        ``max_output_tokens`` is refused with the field (never silently
        clamped, the allocator's own rule), and with no stored ceiling
        nothing bounds it — the number stands, uncapped, the same rule
        resolution reads by.
        """
        if not task_key:
            raise ProfileRefusedError(("task_key",), "a task key cannot be empty")
        assignments = self._assignments()
        if profile_id is None:
            await assignments.clear(task_key)
            await self.session.commit()
            return None
        profile = await self._profiles().get(profile_id)
        if profile is None:
            raise ProfileNotFoundError(f"no profile {profile_id}")
        choice = output_profile if output_profile is not None else OutputProfile()
        ceiling = profile.max_output_tokens
        if choice.name == CUSTOM_OUTPUT_PROFILE and ceiling is not None and choice.target > ceiling:
            raise ProfileRefusedError(
                ("output_profile",),
                f"a custom output of {choice.target} tokens is above the model's"
                f" stored ceiling of {ceiling}; pick a number at or under it,"
                " a named profile, or raise the model's max_output_tokens",
            )
        assignment = await assignments.set(task_key, profile.id, choice.name, choice.custom)
        await self.session.commit()
        return assignment

    def _catalog_info(self, profile: ProviderProfile, provider: LLMProvider) -> ModelInfo | None:
        """The catalog's own fact sheet for the model string — or None.

        The same :func:`effective_info` tiers a generation prices with, the
        same vendor spelling the resolver tries first — asked without the
        row's stored overrides, which the lookup applies to the numbers
        AFTER the tiers decide and so never touched the presence the
        ``in_catalog`` mark states. The known-limit answer must be the
        catalog's own number, not the model row's: the stored ceiling has
        its own column on every read.
        """
        return effective_info(
            profile.model or "",
            vendor=provider.vendor,
            profile_context_window=None,
            profile_max_output_tokens=None,
        )

    async def _last_failure(self, profile_id: UUID) -> tuple[str | None, datetime | None]:
        """The newest audit row of the model, flattened only when it failed.

        One newest-first query per model, user-scoped like every read here —
        and three columns of it (``status``, ``error_code``, ``created_at``),
        never the whole row: prompt and response are up to 64 KB each of
        text no mark reads. The row speaks about the *last* call, so a
        success after a failure is no mark: an ``ok`` row (and a model never
        called) both answer with the empty pair. A code-less ``error`` row
        is the consumer-interrupted stream — the reader walked away, and
        that is not the model's failure — so it leaves the mark off too;
        a coded failure still marks.
        """
        newest = (
            await self.session.execute(
                select(LlmCall.status, LlmCall.error_code, LlmCall.created_at)
                .where(LlmCall.user_id == self.user_id, LlmCall.profile_id == profile_id)
                .order_by(LlmCall.created_at.desc())
                .limit(1)
            )
        ).first()
        if newest is None or newest.status != ERROR or newest.error_code is None:
            return None, None
        return newest.error_code, newest.created_at

    async def _provider_of(self, provider_id: UUID) -> LLMProvider:
        """The user's provider a model write names, or the named refusal.

        The lookup is user-scoped on purpose (Task 1's carry-forward): the
        FK alone would let a model point at another user's provider, and a
        cross-user ``provider_id`` is refused with the field — never
        silently linked.
        """
        provider = await self._providers().get(provider_id)
        if provider is None:
            raise ProfileRefusedError(
                ("provider_id",), f"no provider {provider_id} of yours to point the model at"
            )
        return provider

    async def _paired(self, profile: ProviderProfile) -> LLMProvider:
        """The provider of a stored model, for the reads and probes that need it.

        The write gate keeps the pointer set and the NOT NULL column plus the
        FK keep it dangling nowhere, so this is total for every row the
        writers store; a row that got here anyway is named, not crashed on.
        """
        provider = await self._providers().get(profile.provider_id)
        if provider is None:
            raise ProfileNotFoundError(f"no provider behind model {profile.id}")
        return provider

    def _gate(
        self,
        *,
        provider: LLMProvider,
        context_window: int | None,
        max_output_tokens: int | None,
    ) -> None:
        """Refuse a model that could never answer, naming the fields.

        The endpoint shape is the provider's, and the provider's own gate
        has vetted it; what is left for the model's gate is the output
        reservation that leaves room for input (``max_output_tokens`` below
        ``context_window`` whenever both are known, on the kinds that answer
        real calls — a catalog-merged pair that still leaves no room is
        refused by the allocator — never clamped, D8 — and the writing
        router maps that refusal). Broken config never reaches a model call
        (design, the settings surface).
        """
        if provider.kind not in ("openai-chat", "anthropic"):
            return
        if (
            context_window is not None
            and max_output_tokens is not None
            and max_output_tokens >= context_window
        ):
            raise ProfileRefusedError(
                ("max_output_tokens",),
                "an output reservation that leaves no input room is refused;"
                " set max_output_tokens below context_window",
            )

    async def _unset_other_defaults(self, chosen: ProviderProfile) -> None:
        """Unset every other default, so the flip leaves exactly one holder."""
        profiles = self._profiles()
        for other in await profiles.ordered():
            if other.is_default and other.id != chosen.id:
                await profiles.update(other, is_default=False)
