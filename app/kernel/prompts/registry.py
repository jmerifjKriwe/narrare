"""The prompt registry: the one prompt authority beside the allocator.

A capability's ``prompts.py`` registers its bundled prompts at import time —
there is no central list; ``get_registry`` discovers those modules by
convention (``app/capabilities/*/prompts.py``, folders without one are
skipped) and imports each once, so the process holds one registry. Every
registration carries the bundled Jinja template, a sample-variable factory
(save-time validation, the smoke tests and the editor's variable legend all
render the same sample), an optional contract over the rendered sample, and
whether the key may carry a novel scope. A registration may also carry the
key's live-test assembly (W8): the capability's own callable that gathers
the key's real inputs and renders the draft-or-chain source against them —
the prompts surface's live test consumes it through the spec, never by
reaching into another capability. The key set is closed: users override
keys, they never invent them — an unknown key is a ``KeyError``.

The render itself and its named refusals live in
:mod:`app.kernel.prompts.rendering`; the model and repository of the user-owned
overrides dock here later, on the ``ProviderProfile`` precedent.
"""

import sys
from collections.abc import Awaitable, Callable  # noqa: TC003  the dataclass fields evaluate
from dataclasses import dataclass
from importlib import import_module
from logging import getLogger
from pathlib import Path
from threading import RLock
from uuid import UUID  # noqa: TC003  the dataclass fields evaluate

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002  the context's field evaluates

from app.kernel.embeddings.contract import EmbeddingProvider  # noqa: TC001  the context's field
from app.kernel.llm.resolution import ResolvedProvider  # noqa: TC001  the context's field

REASONS: tuple[str, ...] = (
    "syntax",
    "undefined-variable",
    "include-depth",
    "include-cycle",
    "include-missing",
    "forbidden",
    "runtime",
    "budget",
)
"""The closed refusal vocabulary a ``PromptRenderError.reason`` draws from.

``render`` refuses, it never falls back: a refused render is named so a
caller can frame the failure the way it frames a budget refusal today.
"""


class LiveContextMissingError(RuntimeError):
    """The live test's real assembly found no manuscript data to assemble.

    The live test rides the capability's real context — the scene the writer
    last touched, the chapter's prose, the retrieved passages. A fresh
    instance has none of it, and samples would betray the test's promise, so
    the assembly refuses by this name instead; the caller frames it as its
    no-context face.
    """


@dataclass(frozen=True)
class AssembledContext:
    """The live test's assembled call: the prompt and the facts that rode in.

    ``prompt`` is the rendered source — the editor draft when one was carried,
    the effective chain otherwise — filled with the capability's real context.
    ``facts`` names what rode in, in stable keys the surfaces localize
    (``novel``, ``chapter``, ``passages``, …); the values are the data itself.
    """

    prompt: str
    facts: dict[str, str]


@dataclass(frozen=True)
class LiveTestContext:
    """What a live-test assembly may read: the scope, the draft, the tier.

    ``source`` is the editor draft under test, ``None`` meaning the saved
    effective — the assembly renders it through :func:`render`'s ``source``
    seam, so includes still walk the chain in scope. ``resolved`` is the
    key's task cascade's answer: the tier the call will ride, whose numbers
    the writing assembly budgets with.
    """

    session: AsyncSession
    user_id: UUID
    novel_id: UUID | None
    source: str | None
    resolved: ResolvedProvider
    embeddings: EmbeddingProvider


@dataclass(frozen=True)
class PromptSpec:
    """One registered prompt: the bundled text and what validating it needs.

    ``assemble`` is the capability's own live-test context builder (W8):
    the one callable that gathers the key's real inputs and renders the
    draft-or-chain source against them. ``None`` until a capability docks
    it — the prompts surface's live test refuses a key without one, a
    registration gap the smoke suite names.
    """

    key: str
    template: str
    sample_variables: Callable[[], dict[str, object]]
    contract: Callable[[str], bool] | None = None
    novel_scopable: bool = True
    assemble: Callable[[LiveTestContext], Awaitable[AssembledContext]] | None = None


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
        assemble: Callable[[LiveTestContext], Awaitable[AssembledContext]] | None = None,
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
            assemble=assemble,
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

_BUILD_LOCK = RLock()
"""Serializes the one build; reentrant, so a discovered module's lookup re-enters."""


def _capabilities_dir() -> Path:
    """The capabilities folder the discovery scans; the seam the tests point elsewhere."""
    return Path(__file__).resolve().parents[2] / "capabilities"


def get_registry() -> PromptRegistry:
    """The process's one registry, discovering the capability prompt modules once.

    The instance is published before discovery: a discovered module's
    ``get_registry()`` — the registration idiom, running inside the loop —
    must find the registry being built, not build a second one. The build
    holds a reentrant lock, so a concurrent first call waits for the
    complete registry instead of racing a partial one, and a build that
    raises rolls the publication back — a partial registry never sticks, a
    retry rebuilds. A missing capabilities directory and a prompt module
    that fails to import both contribute nothing rather than taking the
    process down; the smoke suite that renders every bundled prompt catches
    a registration gone missing.
    """
    global _registry
    with _BUILD_LOCK:
        if _registry is not None:
            return _registry
        registry = PromptRegistry()
        _registry = registry
        imported: list[str] = []
        try:
            capabilities = _capabilities_dir()
            if capabilities.is_dir():
                for folder in sorted(capabilities.iterdir()):
                    module = folder / "prompts.py"
                    if folder.is_dir() and module.is_file():
                        name = ".".join(
                            module.relative_to(capabilities.parent.parent).with_suffix("").parts
                        )
                        try:
                            # nosemgrep
                            import_module(name)
                            imported.append(name)
                        except Exception:
                            # A single prompt module that fails to import contributes
                            # nothing rather than taking the process down; the smoke
                            # suite catches a registration gone missing. Log so the
                            # skip is diagnosable instead of silent.
                            getLogger("narrare").warning(
                                "prompt module %s failed to import and was skipped",
                                name,
                                exc_info=True,
                            )
                            continue
        except BaseException:
            # Absolute rollback: a scan/iterdir/BaseException failure mid-discovery
            # must not leave a partial registry published. Drop the modules imported
            # so far from sys.modules so a retry re-imports and re-registers them.
            for name in imported:
                sys.modules.pop(name, None)
            _registry = None
            raise
        return registry
