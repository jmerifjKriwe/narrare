"""The sandboxed render: one environment per call, every failure named.

``render_source`` renders one Jinja source against variables and returns the
text — nothing else touches a template. The environment is
``SandboxedEnvironment`` with ``StrictUndefined`` and no autoescape, built
fresh per call: a render carries no state a later render can see. Its loader
resolves ``{% include 'key' %}`` through the caller's ``include`` callback —
the effective chain (novel row → user-global row → bundled) is the caller's
decision; this module only turns a name into source.

Every refusal names itself with a ``PromptRenderError`` reason: a broken
``{% %}`` is ``syntax``, an unknown ``{{ var }}`` is ``undefined-variable``,
and the include stack refuses ``include-cycle`` (a key already being
rendered above) and ``include-depth`` (deeper than the limit) — both raised
before the deeper body renders, never after. The include tracking is a true
render-time stack: Jinja renders an included template nested inside its
parent's render, and the guard statements wrapped around each included
source open before that body runs and close after it, so sibling includes
may share a key freely while a cycle is still caught. What the ``include``
callback itself raises passes through untouched — the callback owns its
chain's errors.
"""

from collections.abc import Callable, Mapping  # noqa: TC003  signatures evaluate
from typing import Any

from jinja2 import Environment, StrictUndefined, TemplateSyntaxError, UndefinedError
from jinja2.loaders import BaseLoader
from jinja2.sandbox import SandboxedEnvironment

from app.kernel.prompts.registry import PromptRenderError

MAX_INCLUDE_DEPTH = 5
"""The include depth limit: an include that would render one level deeper is refused."""


class _IncludeGuard:
    """The render-time include stack: cycle and depth, refused before deeper rendering.

    One guard per render. ``enter``/``exit`` run as the first and last
    statement of every included source, so the stack holds exactly the keys
    whose bodies are rendering above the current point — a key on the stack
    is a cycle, a stack already at the limit is a chain too deep.
    """

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._stack: list[str] = []

    def enter(self, key: str) -> None:
        if key in self._stack:
            raise PromptRenderError(
                "include-cycle",
                f"the prompt '{key}' is already being rendered above it",
            )
        if len(self._stack) + 1 > self._limit:
            raise PromptRenderError(
                "include-depth",
                f"the prompt '{key}' would render {len(self._stack) + 1} includes "
                f"deep, above the limit of {self._limit}",
            )
        self._stack.append(key)

    def exit(self) -> None:
        self._stack.pop()


class _IncludeLoader(BaseLoader):
    """A loader whose source is the caller's ``include`` callback, guarded in.

    The wrapped source renders the guard calls before and after the included
    body — Jinja's include node drives the nested render itself, so the
    bracket rides in the source rather than in a loader hook. ``{% set %}``
    produces no output; the rendered text stays the template's own.
    """

    def __init__(self, include: Callable[[str], str], guard: _IncludeGuard) -> None:
        self._include = include
        self._guard = guard

    def get_source(
        self, environment: Environment, template: str
    ) -> tuple[str, str | None, Callable[[], bool] | None]:
        source = self._include(template)
        wrapped = (
            f"{{% set _ = _prompt_enter({template!r}) %}}" + source + "{% set _ = _prompt_exit() %}"
        )
        return wrapped, f"<prompt:{template}>", None


def render_source(
    source: str, variables: Mapping[str, object], *, include: Callable[[str], str]
) -> str:
    """Render one template source; every refusal comes back as a named error.

    The environment is built per call — sandboxed, strict, no autoescape —
    and includes resolve through ``include(key) -> source``. A Jinja parse
    failure maps to ``syntax``, an undefined variable at render time to
    ``undefined-variable``; the guard's refusals pass through with their own
    reasons. Anything the ``include`` callback raises is not translated: the
    callback owns the chain it resolves.
    """
    guard = _IncludeGuard(MAX_INCLUDE_DEPTH)
    environment = SandboxedEnvironment(
        undefined=StrictUndefined,
        autoescape=False,
        loader=_IncludeLoader(include, guard),
    )
    # The guard rides the environment globals so every included template
    # resolves it; the root source never names it. The alias is jinja's own
    # signature type for globals — the attribute arrives narrowed to the
    # default namespace's member types, a 3.1.6 typing wart.
    globals_map: dict[str, Any] = environment.globals
    globals_map["_prompt_enter"] = guard.enter
    globals_map["_prompt_exit"] = guard.exit
    try:
        return environment.from_string(source).render(dict(variables))
    except PromptRenderError:
        raise
    except TemplateSyntaxError as error:
        raise PromptRenderError("syntax", str(error)) from None
    except UndefinedError as error:
        raise PromptRenderError("undefined-variable", str(error)) from None
