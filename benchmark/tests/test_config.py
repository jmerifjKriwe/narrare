"""Unit tests for ``benchmark.config`` — loader, validation, redaction.

All tests operate on temporary YAML files; the committed template is
additionally exercised end-to-end (it must stay loader-compatible).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from benchmark.config import (
    TEMPLATE_PATH,
    ApiConfig,
    AuthConfig,
    BenchmarkConfig,
    ConfigError,
    LlmConfig,
    RunConfig,
    StackConfig,
    load_config,
)

if TYPE_CHECKING:
    from pathlib import Path

VALID_YAML = """\
stack:
  project_name: narrare-benchmark
  port_range_low: 18080
  port_range_high: 18180
  mode: containers
  build_image: auto
api:
  base_url: null
  timeout_seconds: 60
auth:
  email: benchmark@example.com
  password: change-me-benchmark-password
llm:
  provider: anthropic
  api_key: sk-test-dummy
  model: claude-sonnet-4-5
  ollama_url: http://localhost:11434
  zai_endpoint: general
run:
  variants: [clean]
  modes: [incremental]
  keep_stack: false
  capabilities: []
"""


def write_config(tmp_path: Path, yaml_text: str = VALID_YAML) -> Path:
    path = tmp_path / "config.local.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    return path


def mutated(old: str, new: str) -> str:
    assert old in VALID_YAML, f"mutation anchor absent: {old!r}"
    return VALID_YAML.replace(old, new)


class TestLoading:
    def test_missing_file_error_points_at_template(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match=r"config\.template\.yaml"):
            load_config(tmp_path / "absent.yaml")

    def test_template_itself_loads(self) -> None:
        config = load_config(TEMPLATE_PATH)
        assert isinstance(config, BenchmarkConfig)

    def test_template_default_stack_mode_is_hybrid(self) -> None:
        config = load_config(TEMPLATE_PATH)
        assert config.stack.mode == "hybrid"

    def test_stack_mode_field_defaults_to_hybrid(self) -> None:
        assert StackConfig("p", 1, 2).mode == "hybrid"

    def test_build_image_field_default_is_auto_containers_only(self) -> None:
        assert StackConfig("p", 1, 2).build_image == "auto"

    def test_absent_stack_mode_defaults_to_hybrid(self, tmp_path: Path) -> None:
        config = load_config(write_config(tmp_path, mutated("  mode: containers\n", "")))
        assert config.stack.mode == "hybrid"

    def test_absent_build_image_defaults_to_auto(self, tmp_path: Path) -> None:
        config = load_config(write_config(tmp_path, mutated("  build_image: auto\n", "")))
        assert config.stack.build_image == "auto"

    def test_old_style_config_without_optional_stack_keys_loads(self, tmp_path: Path) -> None:
        """Configs predating ``mode``/``build_image`` must still load."""
        text = mutated("  mode: containers\n  build_image: auto\n", "")
        config = load_config(write_config(tmp_path, text))
        assert config.stack == StackConfig("narrare-benchmark", 18080, 18180)

    def test_absent_api_origin_defaults_to_trusted_origin(self, tmp_path: Path) -> None:
        config = load_config(write_config(tmp_path))
        assert config.api.origin == "http://localhost:3000"

    def test_template_api_origin_is_the_trusted_default(self) -> None:
        config = load_config(TEMPLATE_PATH)
        assert config.api.origin == "http://localhost:3000"

    def test_api_config_field_default_is_trusted_origin(self) -> None:
        assert ApiConfig(None, 60.0).origin == "http://localhost:3000"

    def test_custom_api_origin_is_parsed(self, tmp_path: Path) -> None:
        text = mutated(
            "  timeout_seconds: 60", '  timeout_seconds: 60\n  origin: "http://127.0.0.1:9999"'
        )
        config = load_config(write_config(tmp_path, text))
        assert config.api.origin == "http://127.0.0.1:9999"

    def test_valid_yaml_parses_every_section(self, tmp_path: Path) -> None:
        config = load_config(write_config(tmp_path))
        assert config.stack == StackConfig(
            "narrare-benchmark", 18080, 18180, "containers", build_image="auto"
        )
        assert config.api == ApiConfig(None, 60.0)
        assert config.auth == AuthConfig("benchmark@example.com", "change-me-benchmark-password")
        assert config.llm == LlmConfig(
            "anthropic",
            "sk-test-dummy",
            "claude-sonnet-4-5",
            "http://localhost:11434",
            "general",
        )
        assert config.run == RunConfig(["clean"], ["incremental"], False, [])

    def test_base_url_override_is_parsed(self, tmp_path: Path) -> None:
        text = mutated("base_url: null", 'base_url: "http://localhost:9999"')
        config = load_config(write_config(tmp_path, text))
        assert config.api.base_url == "http://localhost:9999"

    def test_non_mapping_top_level_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="top level must be a YAML mapping"):
            load_config(write_config(tmp_path, "just-a-string\n"))

    def test_unknown_top_level_section_rejected(self, tmp_path: Path) -> None:
        text = VALID_YAML + "bogus:\n  x: 1\n"
        with pytest.raises(ConfigError, match=r"unknown top-level section.*bogus"):
            load_config(write_config(tmp_path, text))

    def test_section_with_no_fields_rejected(self, tmp_path: Path) -> None:
        text = mutated(
            "  email: benchmark@example.com\n  password: change-me-benchmark-password\n",
            "",
        )
        with pytest.raises(ConfigError, match=r"config\.auth"):
            load_config(write_config(tmp_path, text))


class TestValidation:
    def test_missing_field_rejected(self, tmp_path: Path) -> None:
        text = mutated("  model: claude-sonnet-4-5\n", "")
        with pytest.raises(ConfigError, match=r"config\.llm.*missing key.*\['model'\]"):
            load_config(write_config(tmp_path, text))

    def test_unknown_field_rejected(self, tmp_path: Path) -> None:
        text = mutated("  zai_endpoint: general\n", "  zai_endpoint: general\n  surprise: 1\n")
        with pytest.raises(ConfigError, match=r"unknown key.*surprise"):
            load_config(write_config(tmp_path, text))

    def test_wrong_field_type_rejected(self, tmp_path: Path) -> None:
        text = mutated("  timeout_seconds: 60", "  timeout_seconds: fast")
        with pytest.raises(ConfigError, match=r"config\.api\.timeout_seconds"):
            load_config(write_config(tmp_path, text))

    def test_empty_string_field_rejected(self, tmp_path: Path) -> None:
        text = mutated("  model: claude-sonnet-4-5", '  model: ""')
        with pytest.raises(ConfigError, match="non-empty string"):
            load_config(write_config(tmp_path, text))

    def test_invalid_provider_lists_valid_ids(self, tmp_path: Path) -> None:
        text = mutated("  provider: anthropic", "  provider: claude")
        with pytest.raises(ConfigError, match="anthropic"):
            load_config(write_config(tmp_path, text))

    def test_invalid_zai_endpoint_rejected(self, tmp_path: Path) -> None:
        text = mutated("  zai_endpoint: general", "  zai_endpoint: turbo")
        with pytest.raises(ConfigError, match=r"zai_endpoint"):
            load_config(write_config(tmp_path, text))

    def test_oversized_api_key_error_reports_length_not_value(self, tmp_path: Path) -> None:
        secret = "sk-super-secret-value-123" + "x" * 200
        text = mutated("  api_key: sk-test-dummy", f'  api_key: "{secret}"')
        with pytest.raises(ConfigError, match=r"got \d+-char string") as exc_info:
            load_config(write_config(tmp_path, text))
        message = str(exc_info.value)
        assert secret not in message
        assert "super-secret" not in message  # no partial key substring either
        assert f"got {len(secret)}-char string" in message

    def test_ollama_url_above_step4_maximum_rejected(self, tmp_path: Path) -> None:
        long_url = "http://localhost:11434/" + "a" * 200
        text = mutated("  ollama_url: http://localhost:11434", f'  ollama_url: "{long_url}"')
        with pytest.raises(ConfigError, match=r"config\.llm\.ollama_url.*max_length=200"):
            load_config(write_config(tmp_path, text))

    def test_password_below_register_minimum_rejected(self, tmp_path: Path) -> None:
        text = mutated("  password: change-me-benchmark-password", "  password: short")
        with pytest.raises(ConfigError, match=r"8\.\.72"):
            load_config(write_config(tmp_path, text))

    def test_password_above_register_maximum_rejected(self, tmp_path: Path) -> None:
        text = VALID_YAML.replace("change-me-benchmark-password", "a" * 73)
        with pytest.raises(ConfigError, match=r"8\.\.72"):
            load_config(write_config(tmp_path, text))

    def test_invalid_mode_lists_valid_modes(self, tmp_path: Path) -> None:
        text = mutated("  modes: [incremental]", "  modes: [fast]")
        with pytest.raises(ConfigError, match="incremental"):
            load_config(write_config(tmp_path, text))

    def test_empty_variants_rejected(self, tmp_path: Path) -> None:
        text = mutated("  variants: [clean]", "  variants: []")
        with pytest.raises(ConfigError, match=r"config\.run\.variants"):
            load_config(write_config(tmp_path, text))

    def test_project_name_must_match_compose_rules(self, tmp_path: Path) -> None:
        text = mutated("  project_name: narrare-benchmark", "  project_name: Narrare Benchmark")
        with pytest.raises(ConfigError, match=r"config\.stack\.project_name"):
            load_config(write_config(tmp_path, text))

    def test_port_range_must_be_ordered(self, tmp_path: Path) -> None:
        text = mutated("  port_range_low: 18080", "  port_range_low: 18180").replace(
            "  port_range_high: 18180", "  port_range_high: 18080"
        )
        with pytest.raises(ConfigError, match=r"1 <= low <= high <= 65535"):
            load_config(write_config(tmp_path, text))

    def test_build_image_never_is_parsed(self, tmp_path: Path) -> None:
        text = mutated("  build_image: auto", "  build_image: never")
        config = load_config(write_config(tmp_path, text))
        assert config.stack.build_image == "never"

    def test_invalid_build_image_lists_valid_modes(self, tmp_path: Path) -> None:
        text = mutated("  build_image: auto", "  build_image: always")
        with pytest.raises(ConfigError, match=r"config\.stack\.build_image.*\['auto', 'never'\]"):
            load_config(write_config(tmp_path, text))

    def test_invalid_stack_mode_lists_valid_modes(self, tmp_path: Path) -> None:
        text = mutated("  mode: containers", "  mode: both")
        with pytest.raises(ConfigError, match=r"config\.stack\.mode.*\['containers', 'hybrid'\]"):
            load_config(write_config(tmp_path, text))

    def test_absent_mode_uses_hybrid_default_for_base_url_rule(self, tmp_path: Path) -> None:
        text = mutated("  mode: containers\n", "").replace(
            "base_url: null", 'base_url: "http://localhost:9999"'
        )
        with pytest.raises(ConfigError, match=r"config\.api\.base_url.*hybrid"):
            load_config(write_config(tmp_path, text))

    def test_base_url_rejected_in_hybrid_mode(self, tmp_path: Path) -> None:
        text = mutated("  mode: containers", "  mode: hybrid").replace(
            "base_url: null", 'base_url: "http://localhost:9999"'
        )
        with pytest.raises(ConfigError, match=r"config\.api\.base_url.*hybrid"):
            load_config(write_config(tmp_path, text))

    def test_base_url_must_be_http(self, tmp_path: Path) -> None:
        text = mutated("base_url: null", "base_url: localhost:8000")
        with pytest.raises(ConfigError, match=r"config\.api\.base_url"):
            load_config(write_config(tmp_path, text))

    def test_api_origin_with_path_rejected(self, tmp_path: Path) -> None:
        text = mutated(
            "  timeout_seconds: 60",
            '  timeout_seconds: 60\n  origin: "http://localhost:3000/web"',
        )
        with pytest.raises(ConfigError, match=r"config\.api\.origin.*bare origin"):
            load_config(write_config(tmp_path, text))

    def test_api_origin_with_trailing_slash_rejected(self, tmp_path: Path) -> None:
        text = mutated(
            "  timeout_seconds: 60",
            '  timeout_seconds: 60\n  origin: "http://localhost:3000/"',
        )
        with pytest.raises(ConfigError, match=r"config\.api\.origin.*bare origin"):
            load_config(write_config(tmp_path, text))

    def test_api_origin_with_non_http_scheme_rejected(self, tmp_path: Path) -> None:
        text = mutated(
            "  timeout_seconds: 60",
            '  timeout_seconds: 60\n  origin: "ftp://localhost:3000"',
        )
        with pytest.raises(ConfigError, match=r"config\.api\.origin.*bare origin"):
            load_config(write_config(tmp_path, text))

    def test_non_positive_timeout_rejected(self, tmp_path: Path) -> None:
        text = mutated("  timeout_seconds: 60", "  timeout_seconds: 0")
        with pytest.raises(ConfigError, match=r"config\.api\.timeout_seconds"):
            load_config(write_config(tmp_path, text))


class TestRedaction:
    @pytest.fixture()
    def config(self, tmp_path: Path) -> BenchmarkConfig:
        return load_config(write_config(tmp_path))

    def test_repr_masks_password_and_api_key(self, config: BenchmarkConfig) -> None:
        text = repr(config)
        assert "change-me-benchmark-password" not in text
        assert "sk-test-dummy" not in text
        assert "REDACTED" in text

    def test_str_equals_redacted_repr(self, config: BenchmarkConfig) -> None:
        assert str(config) == repr(config)

    def test_section_reprs_mask_only_secrets(self, config: BenchmarkConfig) -> None:
        assert "REDACTED" in repr(config.auth)
        assert "benchmark@example.com" in repr(config.auth)
        assert "sk-test-dummy" not in repr(config.llm)
        assert "claude-sonnet-4-5" in repr(config.llm)

    def test_redacted_dict_masks_secrets_keeps_rest(self, config: BenchmarkConfig) -> None:
        redacted = config.redacted_dict()
        assert redacted["llm"] == {
            "provider": "anthropic",
            "api_key": "***REDACTED***",
            "model": "claude-sonnet-4-5",
            "ollama_url": "http://localhost:11434",
            "zai_endpoint": "general",
        }
        assert redacted["auth"] == {
            "email": "benchmark@example.com",
            "password": "***REDACTED***",
        }
        assert redacted["run"] == {
            "variants": ["clean"],
            "modes": ["incremental"],
            "keep_stack": False,
            "capabilities": [],
        }
