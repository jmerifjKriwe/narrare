"""CR-08 P1 cross-layer token-limit contract tests.

These tests intentionally read the Frontend TypeScript contract files as text:
the frontend cannot import Python, so Platform owns the parity gate that proves
Core, Backend, and Frontend stayed synchronized.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from narrare.settings.token_limits._validators import VALID_PROFILES
from narrare.settings.token_limits.metadata_service import TokenLimitsMetadataService
from narrare_core.llm.token_profiles import (
    PROFILE_OUTPUT_LIMITS,
    TOKEN_OUTPUT_ABSOLUTE_MAX,
    TOKEN_OUTPUT_UX_RECOMMENDED_MAX,
    public_token_profile_values,
)

pytestmark = pytest.mark.mutation_inert

_ROOT = Path(__file__).resolve().parents[4]
_WEB_TOKEN_PROFILES = _ROOT / "packages" / "web" / "lib" / "token-profiles.ts"
_WEB_SETTINGS_TYPES = _ROOT / "packages" / "web" / "types" / "settings.ts"
_WEB_AI_TAB_CONSTANTS = (
    _ROOT / "packages" / "web" / "components" / "studio" / "settings" / "aiTabConstants.ts"
)
_WEB_TOKEN_PROFILE_SECTION = (
    _ROOT / "packages" / "web" / "components" / "studio" / "settings" / "TokenProfileSection.tsx"
)
_WEB_AI_TAB_TEST = (
    _ROOT
    / "packages"
    / "web"
    / "components"
    / "studio"
    / "settings"
    / "__tests__"
    / "AiTab.test.tsx"
)
_WEB_EDITOR_TOKEN_SETTINGS_TEST = (
    _ROOT
    / "packages"
    / "web"
    / "components"
    / "studio"
    / "editor"
    / "__tests__"
    / "TokenSettings.test.tsx"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _string_literals(source: str, export_name: str) -> tuple[str, ...]:
    match = re.search(
        rf"export const {export_name}[^=]*=\s*\[(?P<body>.*?)\]\s*as const",
        source,
        flags=re.DOTALL,
    )
    assert match is not None, f"missing export const {export_name}"
    return tuple(re.findall(r'"([a-z_]+)"', match.group("body")))


def _number_export(source: str, export_name: str) -> int:
    match = re.search(rf"export const {export_name}\s*=\s*(?P<value>\d+)\s+as const", source)
    assert match is not None, f"missing numeric export {export_name}"
    return int(match.group("value"))


def _profile_output_limits(source: str) -> dict[str, int]:
    match = re.search(
        r"export const PROFILE_OUTPUT_LIMITS[^=]*=\s*\{(?P<body>.*?)\}\s*as const",
        source,
        flags=re.DOTALL,
    )
    assert match is not None, "missing frontend PROFILE_OUTPUT_LIMITS"
    return {key: int(value) for key, value in re.findall(r"(\w+):\s*(\d+)", match.group("body"))}


def _settings_type_values(source: str) -> tuple[str, ...]:
    match = re.search(r"export type TokenLimitProfile\s*=\s*(?P<body>.*?);", source)
    assert match is not None, "missing TokenLimitProfile type"
    return tuple(re.findall(r'"([a-z_]+)"', match.group("body")))


def test_core_backend_and_frontend_public_profiles_are_identical() -> None:
    """Adding/removing/renaming a profile in one layer must break this test."""

    frontend_source = _read(_WEB_TOKEN_PROFILES)
    frontend_values = _string_literals(frontend_source, "TOKEN_PROFILE_VALUES")
    type_values = _settings_type_values(_read(_WEB_SETTINGS_TYPES))
    backend_catalogue = TokenLimitsMetadataService().get_catalogue()
    backend_values = tuple(profile.value for profile in backend_catalogue.profiles)
    core_values = public_token_profile_values()

    assert core_values == ("quick", "balanced", "long_texts", "comprehensive", "custom")
    assert set(core_values) == VALID_PROFILES
    assert backend_values == core_values
    assert frontend_values == core_values
    assert type_values == core_values


def test_preset_maps_and_custom_semantics_match_across_layers() -> None:
    """``custom`` is raw mode everywhere and must never gain a preset limit."""

    frontend_source = _read(_WEB_TOKEN_PROFILES)
    frontend_presets = _string_literals(frontend_source, "TOKEN_PRESET_PROFILE_VALUES")
    frontend_limits = _profile_output_limits(frontend_source)
    backend_catalogue = TokenLimitsMetadataService().get_catalogue()
    backend_limits = {
        profile.value: profile.preset_output_limit
        for profile in backend_catalogue.profiles
        if not profile.is_custom
    }
    backend_custom = [profile for profile in backend_catalogue.profiles if profile.is_custom]

    assert frontend_presets == tuple(PROFILE_OUTPUT_LIMITS)
    assert frontend_limits == PROFILE_OUTPUT_LIMITS
    assert backend_limits == PROFILE_OUTPUT_LIMITS
    assert len(backend_custom) == 1
    assert backend_custom[0].value == "custom"
    assert backend_custom[0].preset_output_limit is None
    assert "custom" not in frontend_limits
    assert "conservative" not in frontend_limits


def test_frontend_options_are_anchored_to_the_contract_not_a_stale_literal() -> None:
    """Frontend option lists must derive from API metadata or the tested constants."""

    constants_source = _read(_WEB_AI_TAB_CONSTANTS)
    section_source = _read(_WEB_TOKEN_PROFILE_SECTION)

    assert "export { TOKEN_PROFILE_VALUES }" in constants_source
    assert "TOKEN_PROFILE_VALUES.map" in constants_source
    assert "metadata?.catalogue" in section_source
    assert "return TOKEN_PROFILES" in section_source


def test_absolute_and_recommended_caps_match_with_ux_protective_evidence() -> None:
    """A 16k UI control is valid only as labelled UX range with custom >16k path."""

    frontend_source = _read(_WEB_TOKEN_PROFILES)
    catalogue = TokenLimitsMetadataService().get_catalogue()

    assert catalogue.absolute_max == TOKEN_OUTPUT_ABSOLUTE_MAX == 131072
    assert catalogue.ux_recommended_max == TOKEN_OUTPUT_UX_RECOMMENDED_MAX == 16000
    assert _number_export(frontend_source, "TOKEN_OUTPUT_ABSOLUTE_MAX") == catalogue.absolute_max
    assert (
        _number_export(frontend_source, "TOKEN_OUTPUT_UX_RECOMMENDED_MAX")
        == catalogue.ux_recommended_max
    )

    section_source = _read(_WEB_TOKEN_PROFILE_SECTION)
    ai_tab_test_source = _read(_WEB_AI_TAB_TEST)
    editor_test_source = _read(_WEB_EDITOR_TOKEN_SETTINGS_TEST)

    assert "metadata?.ux_recommended_max" in section_source
    assert "settings.ai.tokenLimits.recommendedRangeLabel" in section_source
    assert "max={recommendedMax}" in section_source
    assert "max={customMax}" in section_source
    assert "settings.ai.tokenLimits.customOutputLimitLabel" in section_source
    assert "64000" in ai_tab_test_source
    assert "recommendedRangeLabel" in ai_tab_test_source
    assert 'expect(customInput.max).toBe("131072")' in ai_tab_test_source
    assert "64000" in editor_test_source
    assert 'expect(input.max).toBe("131072")' in editor_test_source
