"""The sandboxed render: one environment per call, every failure named.

``render_source`` renders one Jinja source against variables and returns the
text — nothing else touches a template. The environment is
``SandboxedEnvironment`` with ``StrictUndefined``, no autoescape and the
trailing newline kept (a saved template renders byte-identical), built fresh
per call: a render carries no state a later render can see. Its loader
resolves ``{% include 'key' %}`` through the caller's ``include`` callback —
the effective chain (novel row → user-global row → bundled) is the caller's
decision; this module only turns a name into source.

Every refusal names itself with a ``PromptRenderError`` reason: a broken
``{% %}`` is ``syntax``, an unknown ``{{ var }}`` is ``undefined-variable``,
a sandbox violation is ``forbidden``, any other template-time exception is
``runtime``, and an include key the callback cannot resolve (its
``KeyError``) is ``include-missing``. The include stack refuses
``include-cycle`` (a key already being rendered above) and ``include-depth``
(deeper than the limit) — both before the deeper body renders. The stack
lives where template text cannot reach it: the environment hands Jinja every
loaded include wrapped so the bracket enters before the included body's
events and pops in a ``finally`` after them — the source carries no guard
calls and no guard callable is a template global, so a template naming one
finds only StrictUndefined. What the ``include`` callback itself raises
passes through untouched, except that one ``KeyError``. ``budget`` is later
callers' refusal, not this module's.
"""

from collections.abc import (  # noqa: TC003  signatures evaluate
    Callable,
    Iterable,
    Iterator,
    Mapping,
    MutableMapping,
)
from typing import Any, cast

from jinja2 import (
    Environment,
    StrictUndefined,
    Template,
    TemplateSyntaxError,
    UndefinedError,
)
from jinja2.environment import TemplateModule  # noqa: TC002  signatures evaluate
from jinja2.exceptions import SecurityError
from jinja2.loaders import BaseLoader
from jinja2.runtime import Context  # noqa: TC002  signatures evaluate
from jinja2.sandbox import SandboxedEnvironment

from app.kernel.prompts.registry import PromptRenderError

MAX_INCLUDE_DEPTH = 5
"""The include depth limit: an include that would render one level deeper is refused."""


class _IncludeGuard:
    """The render-time include stack: cycle and depth, refused before deeper rendering.

    One guard per render. Every included level's stream enters as its first
    event and pops in a ``finally``, so the stack holds exactly the keys
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
    """A loader whose source is the caller's ``include`` callback.

    A ``KeyError`` from the callback means the chain has no source for the
    key — the one callback error translated, to ``include-missing``; anything
    else the callback raises passes through, the callback's own contract.
    """

    def __init__(self, include: Callable[[str], str]) -> None:
        self._include = include

    def get_source(
        self, environment: Environment, template: str
    ) -> tuple[str, str | None, Callable[[], bool] | None]:
        try:
            source = self._include(template)
        except KeyError as error:
            raise PromptRenderError(
                "include-missing",
                f"the include chain has no source for '{template}' ({error})",
            ) from error
        return source, f"<prompt:{template}>", None


class _GuardedModule:
    """A loaded module whose event stream is bracketed by the guard.

    The without-context include renders through the module's ``_body_stream``;
    this proxy brackets exactly that stream.
    """

    def __init__(self, key: str, guard: _IncludeGuard, inner: TemplateModule) -> None:
        self._key = key
        self._guard = guard
        self._inner = inner

    @property
    def _body_stream(self) -> Iterator[str]:
        self._guard.enter(self._key)
        try:
            yield from self._inner._body_stream  # pyright: ignore[reportPrivateUsage]  jinja names no public accessor for the stream
        finally:
            self._guard.exit()


class _GuardedTemplate:
    """A loaded include whose render is bracketed by the guard stack.

    Jinja's include node drives the nested render itself — through
    ``root_render_func``/``new_context`` with context, through
    ``_get_default_module``/``_body_stream`` without — so the wrapper owns
    exactly those members: each stream enters the guard as its first event
    and pops in a ``finally``, so a refusal or a mid-render exception cannot
    leave the stack unbalanced. The wrapper satisfies the include node's
    protocol and nothing more; :func:`render_source` hands it to Jinja
    behind a ``cast``, and no name on it is reachable from template text.
    """

    def __init__(self, key: str, guard: _IncludeGuard, inner: Template) -> None:
        self._key = key
        self._guard = guard
        self._inner = inner

    def new_context(
        self,
        vars: dict[str, Any] | None = None,
        shared: bool = False,
        locals: Mapping[str, Any] | None = None,
    ) -> Context:
        return self._inner.new_context(vars, shared, locals)

    def root_render_func(self, *args: Any, **kwargs: Any) -> Iterator[str]:
        self._guard.enter(self._key)
        try:
            yield from self._inner.root_render_func(*args, **kwargs)
        finally:
            self._guard.exit()

    def _get_default_module(self, ctx: Context | None = None) -> _GuardedModule:
        return _GuardedModule(
            self._key,
            self._guard,
            self._inner._get_default_module(ctx),  # pyright: ignore[reportPrivateUsage]  the without-context include path
        )


def _guarded(template: Template, guard: _IncludeGuard) -> Template:
    """The include-time face of a loaded template, or the template untouched.

    A template that was not loaded by name — a ``Template`` object passed
    through the variables, outside the prompt contract — has no key to guard
    under and passes through raw. The cast is the wrapper's contract: it
    answers the include node's members and nothing more.
    """
    if template.name is None:
        return template
    return cast("Template", _GuardedTemplate(template.name, guard, template))


class _RenderEnvironment(SandboxedEnvironment):
    """The one per-render environment: sandboxed, strict, includes guarded.

    The pinned options live here and only here. ``get_template`` and
    ``select_template`` wrap what they load, so every include — with and
    without context — renders under the guard; the root source comes from
    ``from_string`` and is never wrapped (depth zero, no key).
    """

    def __init__(self, include: Callable[[str], str], guard: _IncludeGuard) -> None:
        super().__init__(
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
            loader=_IncludeLoader(include),
        )
        self._guard = guard

    def get_template(
        self,
        name: str | Template,
        parent: str | None = None,
        globals: MutableMapping[str, Any] | None = None,
    ) -> Template:
        return _guarded(super().get_template(name, parent, globals), self._guard)

    def select_template(
        self,
        names: Iterable[str | Template],
        parent: str | None = None,
        globals: MutableMapping[str, Any] | None = None,
    ) -> Template:
        return _guarded(super().select_template(names, parent, globals), self._guard)


def render_source(
    source: str, variables: Mapping[str, object], *, include: Callable[[str], str]
) -> str:
    """Render one template source; every refusal comes back as a named error.

    The environment is built per call and includes resolve through
    ``include(key) -> source``. ``syntax``, ``undefined-variable``,
    ``forbidden`` and ``runtime`` map the template's own failures;
    ``include-missing`` the callback's missing key; the guard's
    ``include-cycle`` and ``include-depth`` pass through with their own
    reasons. Anything else the ``include`` callback raises is not
    translated: the callback owns the chain it resolves.
    """
    guard = _IncludeGuard(MAX_INCLUDE_DEPTH)
    environment = _RenderEnvironment(include, guard)
    try:
        return environment.from_string(source).render(dict(variables))
    except PromptRenderError:
        raise
    except TemplateSyntaxError as error:
        raise PromptRenderError("syntax", str(error)) from None
    except UndefinedError as error:
        raise PromptRenderError("undefined-variable", str(error)) from None
    except SecurityError as error:
        raise PromptRenderError("forbidden", str(error)) from None
    except Exception as error:
        raise PromptRenderError("runtime", str(error)) from error
