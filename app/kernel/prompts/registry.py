"""The prompt registry: the one prompt authority beside the allocator.

A capability's ``prompts.py`` registers its bundled prompts at import time —
there is no central list; ``get_registry`` discovers those modules by
convention (``app/capabilities/*/prompts.py``, folders without one are
skipped) and imports each once, so the process holds one registry. Every
registration carries the bundled Jinja template, a sample-variable factory
(save-time validation, the smoke tests and the editor's variable legend all
render the same sample), an optional contract over the rendered sample, and
whether the key may carry a novel scope. The key set is closed: users
override keys, they never invent them — an unknown key is a ``KeyError``.

The render itself and its named refusals live in
:mod:`app.kernel.prompts.render`; the model and repository of the user-owned
overrides dock here later, on the ``ProviderProfile`` precedent.
"""

from collections.abc import Callable  # noqa: TC003  the dataclass fields evaluate
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

REASONS: tuple[str, ...] = (
    "syntax",
    "undefined-variable",
    "include-depth",
    "include-cycle",
    "budget",
)
"""The closed refusal vocabulary a ``PromptRenderError.reason`` draws from.

``render`` refuses, it never falls back: a refused render is named so a
caller can frame the failure the way it frames a budget refusal today.
"""


@dataclass(frozen=True)
class PromptSpec:
    """One registered prompt: the bundled text and what validating it needs."""

    key: str
    template: str
    sample_variables: Callable[[], dict[str, object]]
    contract: Callable[[str], bool] | None = None
    novel_scopable: bool = True


class PromptRenderError(RuntimeError):
    """A render refused by name: ``reason`` is one of ``REASONS``, ``detail`` says more.

    The reason is what a caller maps — the continuation's error frame, a
    failed knowledge job row, chat's error frame; the detail is the message
    for whoever reads the frame. A reason outside the vocabulary is a
    programming error and raises before any frame can show it.
    """

    def __init__(self, reason: str, detail: str) -> None:
        if reason not in REASONS:
            raise ValueError(f"'{reason}' is outside the refusal vocabulary {REASONS}")
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}")


class PromptRegistry:
    """The key → spec map; registration happens at import time, lookup by key.

    A duplicate key is refused with ``ValueError``: two modules claiming one
    key would make the effective chain ambiguous, and silence would bury it.
    """

    def __init__(self) -> None:
        self._specs: dict[str, PromptSpec] = {}

    def register(
        self,
        key: str,
        *,
        template: str,
        sample_variables: Callable[[], dict[str, object]],
        contract: Callable[[str], bool] | None = None,
        novel_scopable: bool = True,
    ) -> None:
        """Register the bundled template under ``key``; a duplicate key is refused."""
        if key in self._specs:
            raise ValueError(f"prompt key '{key}' is already registered")
        self._specs[key] = PromptSpec(
            key=key,
            template=template,
            sample_variables=sample_variables,
            contract=contract,
            novel_scopable=novel_scopable,
        )

    def spec(self, key: str) -> PromptSpec:
        """The spec registered under ``key``; an unknown key is a ``KeyError``."""
        try:
            return self._specs[key]
        except KeyError:
            raise KeyError(f"unknown prompt key: '{key}'") from None

    def keys(self) -> tuple[str, ...]:
        """The registered keys, in registration order."""
        return tuple(self._specs)


_registry: PromptRegistry | None = None


def get_registry() -> PromptRegistry:
    """The process's one registry, discovering the capability prompt modules once.

    The first call imports every ``app/capabilities/*/prompts.py`` — the
    folders without one are skipped — and their registrations land in the
    order the sorted folder names give. Later calls return the same instance;
    a module's import runs once, so its registrations happen once.
    """
    global _registry
    if _registry is not None:
        return _registry
    registry = PromptRegistry()
    capabilities = Path(__file__).resolve().parents[2] / "capabilities"
    for folder in sorted(capabilities.iterdir()):
        if folder.is_dir() and (folder / "prompts.py").is_file():
            import_module(f"app.capabilities.{folder.name}.prompts")
    _registry = registry
    return registry
