"""Typed benchmark configuration model — dataclasses + secret redaction.

Pure data module (no I/O, no validation): instances are produced by
``benchmark.config.load_config`` and validated by
``benchmark.config_validation.parse_sections``. Secrets (``auth.password``,
``llm.api_key``) never appear in ``repr`` or ``str`` of any config object;
``BenchmarkConfig.redacted_dict`` provides a mask-everything view for
logging.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "config.local.yaml"
"""Default local config path (gitignored)."""

TEMPLATE_PATH = Path(__file__).resolve().parent / "config.template.yaml"
"""Committed template every local config must be created from."""

_SECRET = "***REDACTED***"


class ConfigError(ValueError):
    """Raised when the benchmark config is missing or invalid."""


@dataclass(frozen=True)
class StackConfig:
    """Compose stack identity and the host-port scan range."""

    project_name: str
    port_range_low: int
    port_range_high: int


@dataclass(frozen=True)
class ApiConfig:
    """API endpoint settings; ``base_url=None`` derives from the stack port."""

    base_url: str | None
    timeout_seconds: float


@dataclass(frozen=True, repr=False)
class AuthConfig:
    """Benchmark user credentials (seeded via ``POST /auth/register``)."""

    email: str
    password: str

    def __repr__(self) -> str:
        return f"AuthConfig(email={self.email!r}, password={_SECRET!r})"


@dataclass(frozen=True, repr=False)
class LlmConfig:
    """LLM provider settings — mirrors ``Step4ProviderRequest`` fields."""

    provider: str
    api_key: str
    model: str
    ollama_url: str
    zai_endpoint: str

    def __repr__(self) -> str:
        return (
            f"LlmConfig(provider={self.provider!r}, api_key={_SECRET!r}, "
            f"model={self.model!r}, ollama_url={self.ollama_url!r}, "
            f"zai_endpoint={self.zai_endpoint!r})"
        )


@dataclass(frozen=True)
class RunConfig:
    """Run selection: corpus variants, ingest modes, capability filter."""

    variants: list[str]
    modes: list[str]
    keep_stack: bool
    capabilities: list[str]


@dataclass(frozen=True)
class BenchmarkConfig:
    """Root benchmark configuration — one member per template section."""

    stack: StackConfig
    api: ApiConfig
    auth: AuthConfig
    llm: LlmConfig
    run: RunConfig

    def redacted_dict(self) -> dict[str, object]:
        """Nested plain-data view with secrets masked — safe for logging."""
        return {
            "stack": asdict(self.stack),
            "api": asdict(self.api),
            "auth": {**asdict(self.auth), "password": _SECRET},
            "llm": {**asdict(self.llm), "api_key": _SECRET},
            "run": asdict(self.run),
        }
