"""Parity gate tests: one mutation per hand-written surface (all twelve).

Each test copies only the governed surface files into a temporary tree, then
rewrites exactly one fact. ``_mutate`` asserts that the replacement changed the
file, so a mutation string that no longer matches the surface cannot leave a
vacuous green test behind.

Three tests go further and *remove* an anchor (the ``CoreSettings`` class, the
``_test_call`` function, a message file) or corrupt one (malformed JSON): an
anchor a scanner cannot find must be a violation, never an empty result, or the
gate would read as coverage it does not provide.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from scripts.generate_provider_catalog import CATALOG_PATH, load_catalog
from scripts.provider_catalog_parity import check_parity

REPO_ROOT = Path(__file__).resolve().parents[3]

PRICING = "packages/core/narrare_core/llm/model_pricing.py"
CACHE = "packages/core/narrare_core/llm/_providers/cache_settings.py"
MEM0 = "packages/core/narrare_core/memory/mem0_client.py"
REGISTRY = "packages/core/narrare_core/llm/_providers/registry.py"
SETTINGS = "packages/core/narrare_core/settings.py"
PROVIDER_SERVICE = "apps/api/narrare/setup/provider_service.py"

LOCALES = ("en", "de", "fr")
_MESSAGE_FILE = "packages/i18n/messages/{locale}/settings-ai.json"

MUTATED_FILES = (
    PRICING,
    CACHE,
    MEM0,
    REGISTRY,
    SETTINGS,
    PROVIDER_SERVICE,
    *(_MESSAGE_FILE.format(locale=locale) for locale in LOCALES),
)


def _messages(locale: str) -> str:
    """The repo-relative ``settings-ai`` message file of ``locale``."""
    return _MESSAGE_FILE.format(locale=locale)


def _sandbox(tmp_path: Path) -> Path:
    """Copy the Core surfaces into ``tmp_path`` so a mutation stays local."""
    for relative in MUTATED_FILES:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative, destination)
    return tmp_path


def _mutate(root: Path, relative: str, old: str, new: str) -> None:
    """Apply one exact replacement, proving it matched and changed the file."""
    target = root / relative
    before = target.read_text(encoding="utf-8")
    assert old in before, f"mutation string not found in {relative}: {old!r}"
    after = before.replace(old, new)
    assert after != before, f"mutation did not change {relative}"
    target.write_text(after, encoding="utf-8")


def test_pristine_tree_has_no_violations(tmp_path: Path) -> None:
    assert check_parity(load_catalog(CATALOG_PATH), _sandbox(tmp_path)) == []


def test_missing_pricing_key_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        PRICING,
        '    "groq": {"input": 0.5, "output": 1.0},\n',
        "",
    )

    violations = check_parity(load_catalog(CATALOG_PATH), root)

    assert any(
        violation.surface == "pricing.keys" and "groq" in violation.detail
        for violation in violations
    )


def test_disagreeing_pricing_value_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        PRICING,
        '"groq": {"input": 0.5, "output": 1.0}',
        '"groq": {"input": 0.7, "output": 1.0}',
    )

    violations = check_parity(load_catalog(CATALOG_PATH), root)

    matches = [v for v in violations if v.surface == "pricing.values" and "groq" in v.detail]
    assert len(matches) == 1
    assert "0.5" in matches[0].detail
    assert "0.7" in matches[0].detail


def test_duplicate_cache_arm_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        CACHE,
        '        case "ollama":\n            return {}  # No caching support\n',
        '        case "groq":\n            return {}  # No caching support\n',
    )

    violations = check_parity(load_catalog(CATALOG_PATH), root)

    assert any(
        violation.surface == "cache.arms"
        and "groq" in violation.detail
        and "2 match arms" in violation.detail
        for violation in violations
    )


def test_wildcard_before_provider_arms_shadows_them(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        CACHE,
        "    match provider_name:\n",
        "    match provider_name:\n        case _:\n            return {}\n",
    )

    violations = check_parity(load_catalog(CATALOG_PATH), root)

    assert any(
        violation.surface == "cache.arms"
        and "anthropic" in violation.detail
        and "shadowed" in violation.detail
        for violation in violations
    )


def test_cache_body_disagreeing_with_policy_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        CACHE,
        '            return {"cache_control": True}',
        '            return {"cache_control": False}',
    )

    violations = check_parity(load_catalog(CATALOG_PATH), root)

    matches = [v for v in violations if v.surface == "cache.bodies" and "anthropic" in v.detail]
    assert len(matches) == 1
    assert "cache_control" in matches[0].detail
    assert "True" in matches[0].detail
    assert "False" in matches[0].detail


def test_unknown_mem0_key_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        MEM0,
        '"ollama": "llama3.2:3b",',
        '"ollamax": "llama3.2:3b",',
    )

    violations = check_parity(load_catalog(CATALOG_PATH), root)

    assert any(
        violation.surface == "mem0.keys" and "ollamax" in violation.detail
        for violation in violations
    )


def test_empty_mem0_map_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        MEM0,
        '    "anthropic": "claude-haiku-4-20250414",\n'
        '    "openai": "gpt-4.1-nano",\n'
        '    "ollama": "llama3.2:3b",\n'
        '    "zai": "glm-4-flash",\n',
        "",
    )

    violations = check_parity(load_catalog(CATALOG_PATH), root)

    assert any(
        violation.surface == "mem0.keys" and "empty" in violation.detail for violation in violations
    )


def test_provider_without_prefix_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        REGISTRY,
        '    ("ollama/", "ollama"),\n',
        '    ("ollama/", "ollama_local"),\n',
    )
    _mutate(
        root,
        REGISTRY,
        '    ("llama", "ollama"),\n',
        '    ("llama", "ollama_local"),\n',
    )

    violations = check_parity(load_catalog(CATALOG_PATH), root)

    assert any(
        violation.surface == "prefixes.cover" and "ollama" in violation.detail
        for violation in violations
    )


# --- assertion helpers: every test asks one surface for the one fact it mutated ---


def _details(root: Path, surface: str) -> list[str]:
    """The details of every ``surface`` violation in the (possibly mutated) tree."""
    return [
        violation.detail
        for violation in check_parity(load_catalog(CATALOG_PATH), root)
        if violation.surface == surface
    ]


def _naming(root: Path, surface: str, *needles: str) -> list[str]:
    """The ``surface`` violation details that name every given needle."""
    return [detail for detail in _details(root, surface) if all(n in detail for n in needles)]


def test_undeclared_settings_field_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(root, SETTINGS, "    anthropic_api_key: str | None = None\n", "")

    assert _naming(root, "settings.fields", "anthropic", "not declared")


def test_settings_field_with_wrong_env_var_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        SETTINGS,
        "    groq_api_key: str | None = None\n",
        '    groq_api_key: str | None = Field(default=None, validation_alias="GROQ_KEY")\n',
    )

    naming = _naming(root, "settings.fields", "groq")
    assert len(naming) == 1
    assert "GROQ_KEY" in naming[0]
    assert "GROQ_API_KEY" in naming[0]


def test_settings_field_with_unevaluable_alias_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        SETTINGS,
        "    zai_api_key: str | None = None\n",
        "    zai_api_key: str | None = Field(default=None, validation_alias=ALIAS)\n",
    )

    assert _naming(root, "settings.fields", "zai", "cannot evaluate")


def test_absent_settings_class_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(root, SETTINGS, "class CoreSettings(BaseSettings):", "class Renamed(BaseSettings):")

    assert _naming(root, "settings.fields", "anthropic", "CoreSettings")
    assert _naming(root, "apikeys.cover", "anthropic")


def test_api_key_env_without_declared_field_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(root, SETTINGS, "    openai_api_key: str | None = None\n", "")

    assert _naming(root, "apikeys.cover", "openai", "openai_api_key")


def test_missing_fallback_provider_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(root, PROVIDER_SERVICE, "AIProvider.GROQ: [", "AIProvider.PERPLEXITY: [")

    assert _naming(root, "fallback.keys", "groq", "missing")
    assert _naming(root, "fallback.keys", "perplexity", "extra")


def test_absent_fallback_table_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        PROVIDER_SERVICE,
        "_FALLBACK_MODELS: dict[AIProvider, list[ProviderModel]] = {",
        "_RENAMED_FALLBACK_MODELS: dict[AIProvider, list[ProviderModel]] = {",
    )

    assert _naming(root, "fallback.keys", "anthropic", "_FALLBACK_MODELS", "not a dict literal")


def test_disagreeing_fallback_model_id_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(root, PROVIDER_SERVICE, 'id="llama-3.3-70b-versatile"', 'id="llama-3.1-70b-versatile"')

    naming = _naming(root, "fallback.ids", "groq")
    assert len(naming) == 1
    assert "llama-3.3-70b-versatile" in naming[0]
    assert "llama-3.1-70b-versatile" in naming[0]


def test_endpoint_selector_provider_without_test_call_branch_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(
        root,
        PROVIDER_SERVICE,
        "elif provider == AIProvider.OLLAMA:",
        "elif provider == AIProvider.OLLAMA_CLOUD:",
    )

    assert _naming(root, "testcall.endpoints", "ollama")
    assert not _naming(root, "testcall.endpoints", "zai")


def test_absent_test_call_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    _mutate(root, PROVIDER_SERVICE, "async def _test_call(", "async def _renamed_call(")

    for provider in ("ollama", "zai"):
        assert _naming(root, "testcall.endpoints", provider, "_test_call")


@pytest.mark.parametrize("locale", LOCALES)
def test_label_key_missing_in_a_locale_is_reported(tmp_path: Path, locale: str) -> None:
    root = _sandbox(tmp_path)
    _mutate(root, _messages(locale), '    "zai": "Z.AI",', '    "zaii": "Z.AI",')

    assert _naming(root, "labels.locales", "zai", f"messages/{locale}/")


def test_absent_locale_file_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    (root / _messages("fr")).unlink()

    assert _naming(root, "labels.locales", "anthropic", "messages/fr/")


def test_malformed_locale_file_is_reported(tmp_path: Path) -> None:
    root = _sandbox(tmp_path)
    (root / _messages("de")).write_text('{"providers": {', encoding="utf-8")

    assert _naming(root, "labels.locales", "groq", "messages/de/", "not valid UTF-8 JSON")
