"""Idempotent benchmark provisioning — user + LLM config via the normal user path.

Implements the verified runner provisioning path (``benchmark/docs/api-surface.md``
§2/§3): ``register`` with fallback ``login`` on the documented duplicate-email
statuses (§2.1: "Repeat registration = 400/409"), an already-configured
short-circuit on ``GET /auth/me`` → ``has_providers: true`` (§2.5 — a second
``complete`` would create a duplicate novel; §3 explicitly warns that
``complete`` creates one), the provider validation ``POST /setup/validate/step-4``
(marked optional by the map's runner path; included as fail-fast: the provider
key is verified BEFORE anything is persisted), and the single authenticated
``POST /setup/complete`` with a full ``WizardState`` (``starter=blank`` per §3's
runner path; provider fields mirror ``config.llm`` field-for-field per the
``Step4ProviderRequest`` shape, §3.4).

No env-var plane is used or offered — this module speaks the production user
path exclusively (spec §6). The wizard steps 1-3 validations are NOT called:
§3 defines steps 1-4 as independent validations and the documented runner path
is "register/login → (optional step-4 validation) → complete".

Secrets discipline: ``config.llm.api_key`` travels in request bodies only.
The module logs nothing, and every error message is built from status codes,
endpoint paths, field names, and server-provided messages — never from
request payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, cast

from benchmark.client import ApiError

if TYPE_CHECKING:
    import httpx

    from benchmark.client import BenchmarkClient
    from benchmark.config import BenchmarkConfig, LlmConfig

_ME_PATH: Final[str] = "/api/v1/auth/me"
_STEP4_PATH: Final[str] = "/api/v1/setup/validate/step-4"
_COMPLETE_PATH: Final[str] = "/api/v1/setup/complete"

_USER_EXISTS_STATUSES: Final[frozenset[int]] = frozenset({400, 409})
"""§2.1: duplicate-email registration fails with 400 or 409 → login instead."""

_DISPLAY_NAME: Final[str] = "KB Benchmark"
_PROJECT_NAME: Final[str] = "kb-benchmark"
_WRITING_LANGUAGE: Final[str] = "de"
"""German — the corpus flowing into this novel is German (plan global constraints)."""
_AUTOSAVE_INTERVAL: Final[int] = 30
_NOVEL_TITLE: Final[str] = "KB Benchmark Corpus"
_AUTHOR: Final[str] = ""
_GENRE: Final[str] = ""
_LOGLINE: Final[str] = ""
_STORY_STRUCTURE: Final[str] = "three_act"
_TONE: Final[str] = "dramatic"
_STARTER: Final[str] = "blank"


class ProvisioningError(RuntimeError):
    """Provisioning could not be completed or verified against the map.

    Message contract: payload-free (status codes, paths, field names,
    server-provided text only) — safe to log.
    """


@dataclass(frozen=True)
class ProvisionOutcome:
    """What provisioning established on the target stack.

    ``novel_id`` is ``None`` when the stack was already configured (the
    short-circuit path never calls ``complete``, so no novel is created).
    """

    already_configured: bool
    novel_id: str | None


def provision(client: BenchmarkClient, config: BenchmarkConfig) -> ProvisionOutcome:
    """Ensure the benchmark user and LLM provider config exist — idempotently.

    Sequence (map §2/§3): register (fallback login on 400/409) →
    ``GET /auth/me`` short-circuit when ``has_providers`` → step-4 provider
    validation → ``POST /setup/complete``. Raises ``ApiError`` for HTTP
    failures and ``ProvisioningError`` when a response shape or validation
    verdict contradicts the map.
    """
    _ensure_user(client, config)
    if _has_providers(client):
        return ProvisionOutcome(already_configured=True, novel_id=None)
    _validate_provider(client, config.llm)
    return ProvisionOutcome(already_configured=False, novel_id=_complete_wizard(client, config.llm))


def _ensure_user(client: BenchmarkClient, config: BenchmarkConfig) -> None:
    """Authenticate the benchmark user: register, or login when it exists."""
    auth = config.auth
    try:
        client.register(auth.email, auth.password, display_name=_DISPLAY_NAME)
    except ApiError as error:
        if error.status not in _USER_EXISTS_STATUSES:
            raise
        client.login(auth.email, auth.password)


def _has_providers(client: BenchmarkClient) -> bool:
    """Read ``has_providers`` from ``GET /auth/me`` (§2.5), shape-checked."""
    body = _json_object(client.request("GET", _ME_PATH), _ME_PATH)
    has_providers = body.get("has_providers")
    if not isinstance(has_providers, bool):
        raise ProvisioningError(f"{_ME_PATH}: 'has_providers' missing or not a boolean")
    return has_providers


def _validate_provider(client: BenchmarkClient, llm: LlmConfig) -> None:
    """``POST /setup/validate/step-4`` — fail fast on an invalid provider config."""
    response = client.request("POST", _STEP4_PATH, json=_provider_payload(llm))
    body = _json_object(response, _STEP4_PATH)
    if body.get("valid") is not True:
        message = body.get("validation_message")
        raise ProvisioningError(f"{_STEP4_PATH}: provider validation failed: {message!r}")


def _complete_wizard(client: BenchmarkClient, llm: LlmConfig) -> str:
    """``POST /setup/complete`` with the full ``WizardState``; returns the novel id."""
    state: dict[str, object] = {
        "project_name": _PROJECT_NAME,
        "writing_language": _WRITING_LANGUAGE,
        "autosave_interval": _AUTOSAVE_INTERVAL,
        "title": _NOVEL_TITLE,
        "author": _AUTHOR,
        "genre": _GENRE,
        "logline": _LOGLINE,
        "story_structure": _STORY_STRUCTURE,
        "tone": _TONE,
        "starter": _STARTER,
        **_provider_payload(llm),
        "skip_provider": False,
    }
    response = client.request("POST", _COMPLETE_PATH, json={"state": state})
    body = _json_object(response, _COMPLETE_PATH)
    novel_id = body.get("novel_id")
    if not isinstance(novel_id, str) or not novel_id:
        raise ProvisioningError(f"{_COMPLETE_PATH}: response missing non-empty 'novel_id'")
    return novel_id


def _provider_payload(llm: LlmConfig) -> dict[str, str]:
    """``Step4ProviderRequest`` field-for-field from ``config.llm`` (§3.4)."""
    return {
        "provider": llm.provider,
        "api_key": llm.api_key,
        "model": llm.model,
        "ollama_url": llm.ollama_url,
        "zai_endpoint": llm.zai_endpoint,
    }


def _json_object(response: httpx.Response, path: str) -> dict[str, object]:
    """Parse a response body as a JSON object per the client's cast idiom."""
    payload: object = response.json()
    if not isinstance(payload, dict):
        raise ProvisioningError(f"{path}: response is not a JSON object")
    return cast("dict[str, object]", payload)
