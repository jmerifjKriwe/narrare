"""Strict benchmark-config validation — template parity, types, value rules.

Consumed by ``benchmark.config.load_config``; every failure carries a
precise ``config.<section>.<field>`` message naming the committed template.
Field semantics mirror the verified API surface
(``benchmark/docs/api-surface.md``): the ``llm`` section mirrors
``Step4ProviderRequest`` (setup wizard step 4, incl. max lengths);
``auth.password`` mirrors the ``RegisterRequest`` length bounds (8..72);
email format is validated server-side (``EmailStr``) and not duplicated.
"""

from __future__ import annotations

import re
from collections.abc import Sized
from typing import TYPE_CHECKING, cast

from benchmark.config_schemas import (
    DEFAULT_API_ORIGIN,
    DEFAULT_BUILD_IMAGE,
    DEFAULT_STACK_MODE,
    TEMPLATE_PATH,
    ApiConfig,
    AuthConfig,
    BenchmarkConfig,
    ConfigError,
    LlmConfig,
    RunConfig,
    StackConfig,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

_VALID_PROVIDERS = frozenset(
    {"anthropic", "openai", "google", "groq", "ollama", "openrouter", "zai"}
)
"""Valid ``llm.provider`` ids — the ``AIProvider`` enum (api-surface.md §3)."""

_VALID_ZAI_ENDPOINTS = frozenset({"general", "coding"})
_VALID_MODES = frozenset({"incremental", "import"})
_VALID_BUILD_IMAGE_MODES = frozenset({"auto", "never"})
_VALID_STACK_MODES = frozenset({"hybrid", "containers"})
_PROJECT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_ORIGIN_RE = re.compile(r"^https?://[a-zA-Z0-9._-]+(?::[0-9]{1,5})?$")
"""Bare origin ``scheme://host[:port]`` — no path, no trailing slash, no
userinfo/query/fragment. The CSRF middleware exact-matches this string
against its trusted list (``middleware.py``), so anything else would 403."""
_SECTIONS = ("stack", "api", "auth", "llm", "run")


def _str_field(section: Mapping[str, object], path: str) -> str:
    value = section.get(path.rsplit(".", 1)[-1])
    if not isinstance(value, str) or not value:
        raise ConfigError(f"config.{path} must be a non-empty string, got {value!r}")
    return value


def _secret_value_shape(value: object) -> str:
    """Describe a rejected secret's type + length — never the value itself."""
    if isinstance(value, Sized):
        return f"{type(value).__name__} (len {len(value)})"
    return type(value).__name__


def _secret_str_field(section: Mapping[str, object], path: str) -> str:
    """Like ``_str_field`` for secret fields — errors carry type/length only."""
    value = section.get(path.rsplit(".", 1)[-1])
    if not isinstance(value, str) or not value:
        shape = _secret_value_shape(value)
        raise ConfigError(f"config.{path} must be a non-empty string, got {shape}")
    return value


def _int_field(section: Mapping[str, object], path: str) -> int:
    value = section.get(path.rsplit(".", 1)[-1])
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"config.{path} must be an integer, got {value!r}")
    return value


def _number_field(section: Mapping[str, object], path: str) -> float:
    value = section.get(path.rsplit(".", 1)[-1])
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"config.{path} must be a number, got {value!r}")
    return float(value)


def _bool_field(section: Mapping[str, object], path: str) -> bool:
    value = section.get(path.rsplit(".", 1)[-1])
    if not isinstance(value, bool):
        raise ConfigError(f"config.{path} must be a boolean, got {value!r}")
    return value


def _str_list_field(section: Mapping[str, object], path: str) -> list[str]:
    value = section.get(path.rsplit(".", 1)[-1])
    if not isinstance(value, list):
        raise ConfigError(f"config.{path} must be a list of strings, got {value!r}")
    items = cast("list[object]", value)
    if any(not isinstance(item, str) for item in items):
        raise ConfigError(f"config.{path} must be a list of strings, got {items!r}")
    return [item for item in items if isinstance(item, str)]


def _section(
    raw: Mapping[str, object],
    name: str,
    keys: tuple[str, ...],
    optional: tuple[str, ...] = (),
) -> Mapping[str, object]:
    """Fetch a top-level section and enforce exact template key parity.

    Keys listed in ``optional`` may be absent (their documented default
    applies); when present they are still known keys and validated as
    usual. Unknown keys are always rejected.
    """
    value = raw.get(name)
    if not isinstance(value, dict):
        raise ConfigError(
            f"config.{name}: missing section or not a mapping — copy it from {TEMPLATE_PATH.name}"
        )
    section = cast("dict[str, object]", value)
    missing = [key for key in keys if key not in section and key not in optional]
    unknown = sorted(str(key) for key in section if key not in keys)
    if missing:
        raise ConfigError(f"config.{name}: missing key(s) {missing} — see {TEMPLATE_PATH.name}")
    if unknown:
        raise ConfigError(f"config.{name}: unknown key(s) {unknown} — expected {list(keys)}")
    return section


def _parse_stack(raw: Mapping[str, object]) -> StackConfig:
    section = _section(
        raw,
        "stack",
        ("project_name", "port_range_low", "port_range_high", "mode", "build_image"),
        optional=("mode", "build_image"),
    )
    project_name = _str_field(section, "stack.project_name")
    if not _PROJECT_NAME_RE.fullmatch(project_name):
        raise ConfigError(
            f"config.stack.project_name {project_name!r} must match "
            f"{_PROJECT_NAME_RE.pattern} (docker compose project-name rules)"
        )
    low = _int_field(section, "stack.port_range_low")
    high = _int_field(section, "stack.port_range_high")
    if not 1 <= low <= high <= 65535:
        raise ConfigError(
            f"config.stack port range must satisfy 1 <= low <= high <= 65535, got [{low}, {high}]"
        )
    mode = _str_field(section, "stack.mode") if "mode" in section else DEFAULT_STACK_MODE
    if mode not in _VALID_STACK_MODES:
        raise ConfigError(f"config.stack.mode {mode!r} is not one of {sorted(_VALID_STACK_MODES)}")
    build_image = (
        _str_field(section, "stack.build_image")
        if "build_image" in section
        else DEFAULT_BUILD_IMAGE
    )
    if build_image not in _VALID_BUILD_IMAGE_MODES:
        raise ConfigError(
            f"config.stack.build_image {build_image!r} is not one of "
            f"{sorted(_VALID_BUILD_IMAGE_MODES)}"
        )
    return StackConfig(project_name, low, high, mode, build_image)


def _parse_api(raw: Mapping[str, object]) -> ApiConfig:
    section = _section(
        raw,
        "api",
        ("base_url", "timeout_seconds", "origin"),
        optional=("origin",),
    )
    base_url = section.get("base_url")
    if base_url is not None and (
        not isinstance(base_url, str) or not base_url.startswith(("http://", "https://"))
    ):
        raise ConfigError(
            f"config.api.base_url must be null or an http(s):// URL, got {base_url!r}"
        )
    timeout = _number_field(section, "api.timeout_seconds")
    if timeout <= 0:
        raise ConfigError(f"config.api.timeout_seconds must be > 0, got {timeout}")
    origin = _str_field(section, "api.origin") if "origin" in section else DEFAULT_API_ORIGIN
    if not _ORIGIN_RE.fullmatch(origin):
        raise ConfigError(
            f"config.api.origin {origin!r} must be a bare origin "
            "(scheme://host[:port], no path or trailing slash)"
        )
    return ApiConfig(base_url, timeout, origin)


def _parse_auth(raw: Mapping[str, object]) -> AuthConfig:
    section = _section(raw, "auth", ("email", "password"))
    password = _secret_str_field(section, "auth.password")
    if not 8 <= len(password) <= 72:
        raise ConfigError(
            f"config.auth.password length {len(password)} violates RegisterRequest bounds 8..72"
        )
    return AuthConfig(_str_field(section, "auth.email"), password)


def _parse_llm(raw: Mapping[str, object]) -> LlmConfig:
    section = _section(raw, "llm", ("provider", "api_key", "model", "ollama_url", "zai_endpoint"))
    provider = _str_field(section, "llm.provider")
    if provider not in _VALID_PROVIDERS:
        raise ConfigError(
            f"config.llm.provider {provider!r} is not one of {sorted(_VALID_PROVIDERS)}"
        )
    api_key = section.get("api_key")
    if not isinstance(api_key, str):
        # Never render the value (secret) — report the type name only.
        raise ConfigError(
            "config.llm.api_key must be a string of at most 200 chars, "
            f"got {type(api_key).__name__}"
        )
    if len(api_key) > 200:
        raise ConfigError(
            "config.llm.api_key must be a string of at most 200 chars, "
            f"got {len(api_key)}-char string"
        )
    model = _str_field(section, "llm.model")
    if len(model) > 200:
        raise ConfigError("config.llm.model exceeds Step4ProviderRequest max_length=200")
    zai_endpoint = _str_field(section, "llm.zai_endpoint")
    if zai_endpoint not in _VALID_ZAI_ENDPOINTS:
        raise ConfigError(
            f"config.llm.zai_endpoint {zai_endpoint!r} is not one of {sorted(_VALID_ZAI_ENDPOINTS)}"
        )
    ollama_url = _str_field(section, "llm.ollama_url")
    if len(ollama_url) > 200:
        raise ConfigError("config.llm.ollama_url exceeds Step4ProviderRequest max_length=200")
    return LlmConfig(provider, api_key, model, ollama_url, zai_endpoint)


def _parse_run(raw: Mapping[str, object]) -> RunConfig:
    section = _section(raw, "run", ("variants", "modes", "keep_stack", "capabilities"))
    variants = _str_list_field(section, "run.variants")
    if not variants:
        raise ConfigError("config.run.variants must list at least one corpus variant")
    modes = _str_list_field(section, "run.modes")
    invalid_modes = sorted(set(modes) - _VALID_MODES)
    if not modes or invalid_modes:
        raise ConfigError(
            f"config.run.modes must be a non-empty subset of {sorted(_VALID_MODES)}, "
            f"got {modes!r} (unknown: {invalid_modes})"
        )
    return RunConfig(
        variants,
        modes,
        _bool_field(section, "run.keep_stack"),
        _str_list_field(section, "run.capabilities"),
    )


def parse_sections(raw: Mapping[str, object]) -> BenchmarkConfig:
    """Validate the raw top-level mapping and build the typed config."""
    unknown = sorted(str(key) for key in raw if key not in _SECTIONS)
    missing = [name for name in _SECTIONS if name not in raw]
    if unknown or missing:
        raise ConfigError(
            f"unknown top-level section(s) {unknown}, missing section(s) "
            f"{missing} — expected {list(_SECTIONS)}, see {TEMPLATE_PATH.name}"
        )
    stack = _parse_stack(raw)
    api = _parse_api(raw)
    # Hybrid spawns the API itself on a stack-selected port — a pinned
    # base_url would point the client somewhere the runner does not control.
    if stack.mode == "hybrid" and api.base_url is not None:
        raise ConfigError(
            "config.api.base_url must be null when stack.mode is hybrid — "
            "the runner spawns the API itself and derives the URL from the "
            "selected port"
        )
    return BenchmarkConfig(
        stack=stack,
        api=api,
        auth=_parse_auth(raw),
        llm=_parse_llm(raw),
        run=_parse_run(raw),
    )
