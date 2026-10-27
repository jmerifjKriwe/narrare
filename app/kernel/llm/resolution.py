"""The resolution cascade: which provider serves one task for one user.

Five tiers, first hit wins: the task's own assignment, an assignment standing
in for the task's capability segment (its first dot-separated name), the
user's default profile, the environment tier, and the fake. The environment
tier reads the same ``NARRE_LLM_PROVIDER`` the process-wide choice always
did — semantics unchanged, so a fresh clone and a headless CI run keep
answering with zero setup — with ``openai-compatible`` as the accepted alias
naming the ``openai-chat`` adapter. The floor is the fake: no configuration
anywhere still answers.

The resolved structure is what the call is audited with and what later work
consumes: the profile that served, its kind and model, and the numeric
tunables — the profile's stored columns where set, the catalog's where it
knows the model, ``None`` where neither does. ``settings.test`` sits in
:data:`KNOWN_TASK_KEYS` because the settings surface audits its probe calls
under it; an unlisted key resolves all the same, so a new capability ships
before its key is listed.
"""

from collections.abc import Callable  # noqa: TC003
from dataclasses import dataclass, field
from os import environ
from uuid import UUID  # noqa: TC003

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.llm.catalog import effective_info
from app.kernel.llm.contract import TextProvider  # noqa: TC001  the dataclass field names it
from app.kernel.llm.fake import FakeProvider
from app.kernel.llm.models import PROFILE_KINDS, ProviderProfile
from app.kernel.llm.openai_chat import DEFAULT_BASE_URL, OpenAIChatProvider
from app.kernel.llm.profiles import AssignmentRepository, ProfileRepository
from app.kernel.secrets import load_key
from app.kernel.vendor import needs_api_key

KNOWN_TASK_KEYS: tuple[str, ...] = (
    "writing.continuation",
    "chat.ask",
    "knowledge.extract-entities",
    "knowledge.check-consistency",
    "settings.test",
)

ENV_PROVIDERS: dict[str, Callable[[], TextProvider]] = {
    "fake": FakeProvider,
    "openai-compatible": OpenAIChatProvider.from_environment,
}
"""The environment tier's entries: what ``NARRE_LLM_PROVIDER`` may name."""


@dataclass(frozen=True)
class ResolvedProvider:
    """One task's provider for one user, with the facts the call is audited with.

    ``provider`` answers; everything else describes the choice. The numeric
    fields are the profile's stored columns merged with the catalog's
    (:func:`app.kernel.llm.catalog.effective_info`) — ``None`` when neither
    knows. ``api_key`` is the plaintext the profile's tier produced; it never
    reaches a log line, a response, an audit row, or a repr — the dataclass
    keeps it out of the generated one.
    """

    provider: TextProvider
    profile_id: UUID | None
    kind: str
    model: str
    context_window: int | None
    max_output_tokens: int | None
    temperature: float | None
    request_timeout: float | None
    base_url: str | None
    api_key: str | None = field(default=None, repr=False)


async def resolve_provider(session: AsyncSession, user_id: UUID, task_key: str) -> ResolvedProvider:
    """Resolve the provider for one user's task, down the five-tier cascade.

    Reads only, on the caller's session: resolution never writes, so the
    request's own transaction stays the only one. A task assignment whose
    profile is gone (the database cascades the assignment with the profile)
    falls through to the next tier without a sound, and a profile whose key
    its tier can no longer produce raises :class:`app.kernel.secrets.KeyUnavailableError`
    — the message names the profile, never the key — before any call runs.
    """
    assignments = AssignmentRepository(session, user_id)
    assignment = await assignments.for_task(task_key)
    if assignment is None:
        assignment = await assignments.for_prefix(task_key.split(".")[0])
    profiles = ProfileRepository(session, user_id)
    profile = await profiles.get(assignment.profile_id) if assignment is not None else None
    if profile is None:
        ordered = await profiles.ordered()  # the default first, then by name
        profile = ordered[0] if ordered else None
    if profile is not None:
        return from_profile(profile)
    return environment_provider()


def environment_provider() -> ResolvedProvider:
    """The environment tier: ``NARRE_LLM_PROVIDER`` decides, semantics unchanged.

    ``openai-compatible`` names the ``openai-chat`` adapter reading
    ``NARRE_LLM_BASE_URL``/``NARRE_LLM_MODEL``/``NARRE_LLM_API_KEY`` — the
    audit's kind column records the adapter's name, which is the only change.
    ``fake`` (and an unset variable) answer with the fake; anything else
    refuses loudly, exactly as the process-wide choice always did.
    """
    name = environ.get("NARRE_LLM_PROVIDER", "fake")
    if name not in ENV_PROVIDERS:
        raise RuntimeError(
            f"unknown LLM provider {name!r}; known: {', '.join(sorted(ENV_PROVIDERS))}"
        )
    if name == "openai-compatible":
        chat = OpenAIChatProvider.from_environment()
        provider: TextProvider = chat
        kind, model = "openai-chat", chat.model
        base_url: str | None = chat.base_url
        api_key: str | None = chat.api_key
    else:
        provider = ENV_PROVIDERS[name]()
        kind, model = "fake", "fake"
        base_url = api_key = None
    context_window, max_output_tokens = _merged(model, None, None)
    return ResolvedProvider(
        provider=provider,
        profile_id=None,
        kind=kind,
        model=model,
        context_window=context_window,
        max_output_tokens=max_output_tokens,
        temperature=None,
        request_timeout=None,
        base_url=base_url,
        api_key=api_key,
    )


def from_profile(profile: ProviderProfile) -> ResolvedProvider:
    """The profile tiers' resolution: the profile's own provider and columns.

    The cascade calls this with the profile it chose; the settings surface
    calls it with the profile a probe names, so both build the identical
    provider from the identical columns. A profile whose key its tier can no
    longer produce raises :class:`app.kernel.secrets.KeyUnavailableError`
    before any call runs — except a local endpoint configured without a key,
    which never had one to lose (the settings gate allows exactly that).
    """
    if profile.kind == "openai-chat":
        base_url = (profile.base_url or DEFAULT_BASE_URL).rstrip("/")
        api_key: str = _profile_key(profile, base_url)
        provider: TextProvider = OpenAIChatProvider(
            base_url=base_url,
            model=profile.model or "",
            api_key=api_key,
            request_timeout=profile.request_timeout,
            temperature_default=profile.temperature,
        )
        kind, model = "openai-chat", profile.model or ""
    elif profile.kind == "fake":
        # A fake stores no key; its model is free text, ignored for answering
        # and carried through to the audit.
        provider = FakeProvider()
        kind, model = "fake", profile.model or "fake"
        base_url, api_key = "", ""
    else:
        raise ValueError(
            f"profile {profile.id} carries unknown kind {profile.kind!r};"
            f" known: {'|'.join(PROFILE_KINDS)}"
        )
    context_window, max_output_tokens = _merged(
        model, profile.context_window, profile.max_output_tokens
    )
    return ResolvedProvider(
        provider=provider,
        profile_id=profile.id,
        kind=kind,
        model=model,
        context_window=context_window,
        max_output_tokens=max_output_tokens,
        temperature=profile.temperature,
        request_timeout=profile.request_timeout,
        # A fake has no endpoint to name; an openai-chat profile always does.
        base_url=base_url or None,
        api_key=api_key or None,
    )


def _profile_key(profile: ProviderProfile, base_url: str) -> str:
    """The profile's key, or the empty no-key of a keyless local endpoint.

    A non-empty column (Fernet ciphertext) or a stored hint (the keyring tier
    wrote the plaintext elsewhere) names a key whichever tier holds it must
    produce again — or refuse by name. Neither, on a local endpoint, is the
    gate-allowed keyless configuration: no key, no header. A remote endpoint
    without a stored key is a row the gate refuses; resolution refuses by
    name instead of calling out silently keyless.
    """
    if profile.api_key or profile.api_key_hint is not None or needs_api_key(base_url):
        return load_key(profile.id, profile.api_key)
    return ""


def _merged(
    model: str, context_window: int | None, max_output_tokens: int | None
) -> tuple[int | None, int | None]:
    """The two window tunables: the caller's stored value, else the catalog's."""
    info = effective_info(
        model, profile_context_window=context_window, profile_max_output_tokens=max_output_tokens
    )
    return (
        context_window if context_window is not None else (info.context_window if info else None),
        max_output_tokens
        if max_output_tokens is not None
        else (info.max_output_tokens if info else None),
    )
