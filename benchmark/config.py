"""Benchmark runner configuration — public facade: loader + re-exports.

Loads ``benchmark/config.local.yaml`` (gitignored — holds real
credentials), which must be created from the committed template
``benchmark/config.template.yaml``. Validation lives in
``benchmark.config_validation`` (template key parity, typed fields,
value rules mirroring the API surface); the typed model with secret
redaction lives in ``benchmark.config_schemas``.

This module is the single public import surface:
``from benchmark.config import load_config, BenchmarkConfig, ...``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import yaml

from benchmark.config_schemas import (
    CONFIG_PATH,
    TEMPLATE_PATH,
    ApiConfig,
    AuthConfig,
    BenchmarkConfig,
    ConfigError,
    LlmConfig,
    RunConfig,
    StackConfig,
)
from benchmark.config_validation import parse_sections

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "CONFIG_PATH",
    "TEMPLATE_PATH",
    "ApiConfig",
    "AuthConfig",
    "BenchmarkConfig",
    "ConfigError",
    "LlmConfig",
    "RunConfig",
    "StackConfig",
    "load_config",
]


def load_config(path: Path = CONFIG_PATH) -> BenchmarkConfig:
    """Load and validate the local benchmark config.

    Raises ``ConfigError`` pointing at the committed template when the
    file is absent or violates the template's structure or constraints.
    """
    if not path.is_file():
        raise ConfigError(
            f"benchmark config not found: {path} — create it from the template: "
            f"cp {TEMPLATE_PATH} {path}"
        )
    loaded: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ConfigError(
            f"{path}: top level must be a YAML mapping with the template's "
            f"sections, got {type(loaded).__name__}"
        )
    return parse_sections(cast("dict[str, object]", loaded))
