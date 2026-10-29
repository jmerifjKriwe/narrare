"""The sandboxed render: one environment per call, every failure named.

``render_source`` renders one Jinja source against variables and returns the
text — nothing else touches a template. The environment is
``SandboxedEnvironment`` with ``StrictUndefined``, no autoescape and the
trailing newline kept (a saved template renders byte-identical), built fresh
per call: a render carries no state a later render can see. Its loader
resolves ``{% include 'key' %}`` through the caller's ``include`` callback —
``render_source`` only turns a name into source. :func:`render` is the chain
walker on top: it picks the source through the effective chain (novel row →
user-global row → bundled) and feeds ``render_source`` the callback that
resolves every include through the same chain in the same scope.

Every refusal names itself with a ``PromptRenderError`` reason: a broken
``{% %}`` is ``syntax``, an unknown ``{{ var }}`` is ``undefined-variable``,
a sandbox violation is ``forbidden``, any other template-time exception is
``runtime``, and an include key the callback cannot resolve (its
``KeyError``) is ``include-missing``. The include stack refuses
``include-cycle`` (a key already being rendered above) and ``include-depth``
(deeper than the limit) — both before the deeper body renders. The stack
lives where template text cannot reach it: the environment hands Jinja every
loaded include wrapped so the bracket enters where the deeper body actually
renders and pops in a ``finally`` after it — the eager without-context load
and the ``root_render_func`` render, with ``{% extends %}`` drawing its
parent through the same bracket — and the source carries no guard calls and
no guard callable is a template global, so a template naming one
finds only StrictUndefined. What the ``include`` callback itself raises
passes through untouched — the callback owns its chain's errors;
infrastructure failing under the chain is an outage, not a refusal — except
the ``KeyError`` of a key it cannot resolve, which becomes
``include-missing``. ``budget`` is later callers' refusal, not this
module's.
"""

import asyncio
from collections.abc import (  # noqa: TC003  signatures evaluate
    Callable,
    Iterable,
    Iterator,
    Mapping,
    MutableMapping,
)
from typing import Any, cast
from uuid import UUID  # noqa: TC003  signatures evaluate

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
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.prompts.models import PromptTemplateRepository
from app.kernel.prompts.registry import PromptRenderError, get_registry

MAX_INCLUDE_DEPTH = 5
"""The include depth limit: an include that would render one level deeper is refused."""


class _IncludeGuard:
    """The render-time include stack: cycle and depth, refused before deeper rendering.

    One guard per render. A deeper body only runs in two places — the eager
    without-context load (``_get_default_module``) and the with-context
    render through ``root_render_func`` — and each of those is bracketed:
    the guard enters before the body runs and pops in a ``finally`` after
    it, so the stack holds exactly the keys whose bodies are rendering
    above the current point — a key on the stack is a cycle, a stack
    already at the limit is a chain too deep.
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


class _CallbackError(Exception):
    """Marks a non-``KeyError`` include-callback failure for untranslated re-raise.

    The callback owns its chain's errors: infrastructure failing under the
    chain is not a prompt refusal, and framing it as one would hide the
    outage behind a 422. The loader wraps the failure only to carry it out
    of Jinja untouched — :func:`render_source` re-raises the original. A
    ``KeyError`` never rides this: it is the ruled ``include-missing``.
    """

    def __init__(self, original: BaseException) -> None:
        super().__init__(str(original))
        self.original = original


class _IncludeLoader(BaseLoader):
    """A loader whose source is the caller's ``include`` callback.

    A ``KeyError`` from the callback means the chain has no source for the
    key — the one callback error translated, to ``include-missing``. Any
    other callback failure rides :class:`_CallbackError` out untranslated:
    the callback owns its chain's errors, this module only carries them.
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
        except Exception as error:
            raise _CallbackError(error) from error
        return source, f"<prompt:{template}>", None


class _GuardedTemplate:
    """A loaded include whose render is bracketed by the guard stack.

    The bracket sits on the load and the render — the two places a deeper
    body actually runs — not on the replay of an already-rendered one: the
    without-context include renders its body eagerly inside
    ``_get_default_module`` (the module's event stream is a materialized
    list), so the guard enters before that call and pops in a ``finally``
    after it; the with-context include renders through
    ``root_render_func``/``new_context``, bracketed the same way, and
    ``{% extends %}`` renders its parent through that bracketed function
    while the extends node reads ``blocks`` off this wrapper. A refusal or a
    mid-render exception cannot leave the stack unbalanced. The wrapper
    satisfies the include and extends nodes' members and nothing more;
    :func:`render_source` hands it to Jinja behind a ``cast``, and no name
    on it is reachable from template text.
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

    def _get_default_module(self, ctx: Context | None = None) -> TemplateModule:
        self._guard.enter(self._key)
        try:
            return self._inner._get_default_module(ctx)  # pyright: ignore[reportPrivateUsage]  the without-context include path
        finally:
            self._guard.exit()

    @property
    def blocks(self) -> dict[str, Callable[..., Iterator[str]]]:
        """The parent's block table, for the extends node's block chaining."""
        return self._inner.blocks


def _guarded(template: Template, guard: _IncludeGuard) -> Template:
    """The include-time face of a loaded template, or the template untouched.

    A template that was not loaded by name — a ``Template`` object passed
    through the variables, outside the prompt contract — has no key to guard
    under and passes through raw. The cast is the wrapper's contract: it
    answers the include and extends nodes' members and nothing more.
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
    except _CallbackError as failure:
        raise failure.original from None
    except TemplateSyntaxError as error:
        raise PromptRenderError("syntax", str(error)) from None
    except UndefinedError as error:
        raise PromptRenderError("undefined-variable", str(error)) from None
    except SecurityError as error:
        raise PromptRenderError("forbidden", str(error)) from None
    except Exception as error:
        raise PromptRenderError("runtime", str(error)) from error


async def render(
    session: AsyncSession,
    user_id: UUID,
    key: str,
    variables: Mapping[str, object],
    *,
    novel_id: UUID | None = None,
) -> str:
    """Render the prompt ``key`` through the effective chain and return the text.

    The source is the user's override in force for the scope — the novel's
    row, else the global one (:meth:`PromptTemplateRepository.effective`) —
    and the registry's bundled template when neither exists. An unknown key
    is a ``KeyError`` before any read: the key set is closed, users override
    keys they never invent them, and the caller frames that as its 404.
    Render failures re-raise ``PromptRenderError`` with their named reason.

    Includes resolve through the same chain in the same scope (same session,
    user and ``novel_id``): the repository owns the preference, and each
    resolved key costs one ``effective()`` lookup — the novel tier first when
    scoped, the global tier behind it; a key included twice costs nothing the
    second time, the environment caching what it loaded. Jinja's loader is
    synchronous while the chain's reads are async, so the render runs off the
    event loop and each include walks back onto it — the loop stays free to
    serve the read, the session never leaves its loop, and a render of a
    template without includes never enters the bridge. A cancelled request
    cannot strand that bridge: the render is shielded and waited out before
    the cancellation is raised, so it — its include reads included — always
    finishes while the session is still the request's, and a cancellation
    re-delivered while the wait lasts is swallowed until the wait is over.
    A key the chain cannot resolve reaches the loader as its
    ``KeyError`` and is refused ``include-missing``; every other failure of
    the lookup — the database being down — passes through untranslated, an
    outage and not a refusal.

    Read-only: no write here, the caller owns the transaction as always.
    """
    registry = get_registry()
    spec = registry.spec(key)  # an unknown key is the caller's 404, not a refusal
    repository = PromptTemplateRepository(session, user_id)
    override = await repository.effective(key, novel_id)
    source = override.content if override is not None else spec.template

    loop = asyncio.get_running_loop()

    def include(name: str) -> str:
        """The include chain: the same walk, one ``effective()`` lookup for the key."""
        included_spec = registry.spec(name)  # unknown -> KeyError -> include-missing
        row = asyncio.run_coroutine_threadsafe(repository.effective(name, novel_id), loop).result()
        return row.content if row is not None else included_spec.template

    inner = asyncio.ensure_future(
        asyncio.to_thread(render_source, source, variables, include=include)
    )
    try:
        return await asyncio.shield(inner)
    except asyncio.CancelledError:
        # The request is going away, but the session is still ours until this
        # coroutine returns: wait the render out so its include reads land on
        # the live session. Cancellation may be re-delivered while we wait
        # (a cancelling scope keeps re-cancelling until its task exits); each
        # delivery is swallowed — the shield keeps the render itself
        # uncancelled — and the caller's cancellation is raised afterwards.
        while not inner.done():
            try:
                await asyncio.shield(inner)
            except asyncio.CancelledError:
                continue
            except Exception:
                break  # the render failed on its own; the cancellation wins
        raise
