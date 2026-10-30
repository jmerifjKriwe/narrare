"""The prompt registry and the sandboxed render, pinned at the unit level.

The boundaries the kernel owns here: a spec round-trips through
``register``/``spec`` with its key set closed (duplicates refused, entry order
kept), and ``render_source`` returns the rendered text when every variable is
given — while each failure mode refuses with ``PromptRenderError`` and its
exact reason: an unknown ``{{ var }}`` is ``undefined-variable``, a broken
``{% %}`` is ``syntax``, a sandbox violation is ``forbidden``, a key the
include callback cannot resolve is ``include-missing``, any other
template-time exception is ``runtime``, a key already being rendered is
``include-cycle``, and an include chain deeper than the limit is
``include-depth``. The include tracking must be a true render-time stack that
template text cannot reach, not a seen-set: a diamond (two sibling includes
of one key) renders, a chain of exactly five includes — the limit — still
renders, and a guard-looking name in template text is simply undefined; the
same bracket holds on the without-context include path (a six-link chain
refuses, five renders, a self-include is a cycle) and on ``{% extends %}``.
A trailing newline survives rendering. ``get_registry`` is the process-wide
instance — a discovered module's registration lands in it, a failed build
leaves nothing published, a missing capabilities directory is skipped —
and, with the first capability docked, carries ``writing.continuation``.
"""

import sys
from pathlib import Path  # noqa: TC003  signatures evaluate

import pytest

from app.kernel.prompts import (
    REASONS,
    PromptRegistry,
    PromptRenderError,
    get_registry,
    render_source,
)
from app.kernel.prompts import registry as prompts_registry


def _toy_registry() -> PromptRegistry:
    """One toy spec carrying every optional field, for the round-trip pins."""
    registry = PromptRegistry()
    registry.register(
        "toy.greeting",
        template="Hello {{ name }}!",
        sample_variables=lambda: {"name": "Ada"},
        contract=lambda text: "Hello" in text,
        novel_scopable=False,
    )
    return registry


def test_register_and_spec_round_trip() -> None:
    spec = _toy_registry().spec("toy.greeting")
    assert spec.key == "toy.greeting"
    assert spec.template == "Hello {{ name }}!"
    assert spec.sample_variables() == {"name": "Ada"}
    assert spec.contract is not None and spec.contract("Hello Ada!")
    assert spec.novel_scopable is False


def test_register_defaults() -> None:
    registry = PromptRegistry()
    registry.register("toy.bare", template="x", sample_variables=lambda: {})
    spec = registry.spec("toy.bare")
    assert spec.contract is None
    assert spec.novel_scopable is True


def test_keys_preserve_entry_order() -> None:
    registry = PromptRegistry()
    for key in ("toy.c", "toy.a", "toy.b"):
        registry.register(key, template="x", sample_variables=lambda: {})
    assert registry.keys() == ("toy.c", "toy.a", "toy.b")


def test_duplicate_key_refused() -> None:
    registry = _toy_registry()
    with pytest.raises(ValueError, match=r"toy\.greeting"):
        registry.register("toy.greeting", template="y", sample_variables=lambda: {})


def test_spec_unknown_key_refused() -> None:
    with pytest.raises(KeyError, match=r"toy\.nope"):
        _toy_registry().spec("toy.nope")


def test_render_with_all_variables() -> None:
    text = render_source("Hello {{ name }}!", {"name": "Ada"}, include=lambda key: "")
    assert text == "Hello Ada!"


def test_render_keeps_trailing_newline() -> None:
    text = render_source("line\n", {}, include=lambda key: "")
    assert text == "line\n"


def test_render_undefined_variable() -> None:
    with pytest.raises(PromptRenderError) as error:
        render_source("Hello {{ missing }}!", {}, include=lambda key: "")
    assert error.value.reason == "undefined-variable"
    assert error.value.detail


def test_render_syntax_error() -> None:
    with pytest.raises(PromptRenderError) as error:
        render_source("Hello {% if %}!", {"name": "Ada"}, include=lambda key: "")
    assert error.value.reason == "syntax"
    assert error.value.detail


def test_render_sandbox_violation_is_forbidden() -> None:
    with pytest.raises(PromptRenderError) as error:
        render_source("{{ ''.__class__ }}", {}, include=lambda key: "")
    assert error.value.reason == "forbidden"
    assert error.value.detail


def test_render_template_runtime_error_is_runtime() -> None:
    with pytest.raises(PromptRenderError) as error:
        render_source("{{ 1/0 }}", {}, include=lambda key: "")
    assert error.value.reason == "runtime"
    assert error.value.detail


def test_render_missing_include_is_include_missing() -> None:
    def missing(key: str) -> str:
        raise KeyError(key)

    with pytest.raises(PromptRenderError) as error:
        render_source("{% include 'gone' %}", {}, include=missing)
    assert error.value.reason == "include-missing"
    assert error.value.detail


def test_render_error_reasons_are_closed() -> None:
    with pytest.raises(ValueError, match="vocabulary"):
        PromptRenderError("crashed", "not a refusal")


def _chain_sources(links: int, suffix: str = "") -> dict[str, str]:
    """`k0` includes `k1` … `k{links}` ends in plain text: `links` includes deep.

    `suffix` rides inside the include tag — `" without context"` for the
    without-context variants of the depth pins.
    """
    return {
        f"k{i}": f"{{% include 'k{i + 1}'{suffix} %}}" if i < links else "END"
        for i in range(links + 1)
    }


def test_render_include_cycle() -> None:
    sources = {"a": "{% include 'b' %}", "b": "{% include 'a' %}"}
    with pytest.raises(PromptRenderError) as error:
        render_source(sources["a"], {}, include=sources.__getitem__)
    assert error.value.reason == "include-cycle"
    assert error.value.detail


def test_render_include_cycle_without_context() -> None:
    """The without-context include path is bracketed like the with-context one."""
    sources = {"a": "{% include 'b' %}", "b": "{% include 'a' without context %}"}
    with pytest.raises(PromptRenderError) as error:
        render_source(sources["a"], {}, include=sources.__getitem__)
    assert error.value.reason == "include-cycle"


def test_render_include_without_context_renders() -> None:
    sources = {"outer": "A{% include 'inner' without context %}B", "inner": "i"}
    text = render_source(sources["outer"], {}, include=sources.__getitem__)
    assert text == "AiB"


def test_render_include_chain_deeper_than_five() -> None:
    sources = _chain_sources(links=6)
    with pytest.raises(PromptRenderError) as error:
        render_source(sources["k0"], {}, include=sources.__getitem__)
    assert error.value.reason == "include-depth"
    assert error.value.detail


def test_render_include_chain_at_limit_renders() -> None:
    sources = _chain_sources(links=5)
    text = render_source(sources["k0"], {}, include=sources.__getitem__)
    assert text == "END"


def test_render_without_context_chain_deeper_than_five() -> None:
    """The without-context include path refuses depth like the with-context one.

    The without-context include renders its body eagerly inside the load, so
    a bracket on the module's event stream only guards the replay — the
    chain renders, the limit never fires. The bracket must sit on the load
    itself for this to refuse.
    """
    sources = _chain_sources(links=6, suffix=" without context")
    with pytest.raises(PromptRenderError) as error:
        render_source(sources["k0"], {}, include=sources.__getitem__)
    assert error.value.reason == "include-depth"
    assert error.value.detail


def test_render_without_context_chain_at_limit_renders() -> None:
    sources = _chain_sources(links=5, suffix=" without context")
    text = render_source(sources["k0"], {}, include=sources.__getitem__)
    assert text == "END"


def test_render_without_context_self_cycle() -> None:
    """A key including itself without context is a cycle, not a recursion crash."""
    sources = {"a": "{% include 'a' without context %}"}
    with pytest.raises(PromptRenderError) as error:
        render_source(sources["a"], {}, include=sources.__getitem__)
    assert error.value.reason == "include-cycle"
    assert error.value.detail


def test_render_extends_renders() -> None:
    """``{% extends %}`` renders through the wrapped parent, blocks chained."""
    sources = {
        "child": "{% extends 'base' %}{% block body %}child{% endblock %}",
        "base": "A{% block body %}base{% endblock %}B",
    }
    text = render_source(sources["child"], {}, include=sources.__getitem__)
    assert text == "AchildB"


def test_render_extends_two_levels_renders() -> None:
    sources = {
        "child": "{% extends 'base' %}{% block body %}child{% endblock %}",
        "base": "[{% extends 'grand' %}{% block inner %}b{% endblock %}]",
        "grand": "G{% block body %}g{% endblock %}/{% block inner %}g{% endblock %}",
    }
    text = render_source(sources["child"], {}, include=sources.__getitem__)
    # base's top-level "[" renders — plain jinja behaves identically here,
    # and the pin is the point.
    assert text == "[Gchild/b"


def test_include_callback_error_passes_through_untranslated() -> None:
    """A non-``KeyError`` callback failure is infrastructure, not a refusal.

    The task-3 callback resolves the effective chain over the database: a
    DB or IO failure must surface as itself, never as a named prompt
    refusal the API would frame as 422.
    """

    def broken(key: str) -> str:
        raise TimeoutError("db down")

    with pytest.raises(TimeoutError, match="db down"):
        render_source("{% include 'x' %}", {}, include=broken)


def test_render_diamond_include_renders() -> None:
    """Two siblings may include one key: the stack refuses cycles, not reuse."""
    sources = {
        "a": "X{% include 'b' %}Y{% include 'c' %}Z",
        "b": "[{% include 'd' %}]",
        "c": "({% include 'd' %})",
        "d": "d",
    }
    text = render_source(sources["a"], {}, include=sources.__getitem__)
    assert text == "X[d]Y(d)Z"


def test_template_text_cannot_reach_the_guard() -> None:
    """A guard-looking name in template text is undefined — never a stack move."""
    with pytest.raises(PromptRenderError) as error:
        render_source("{{ _prompt_exit() }}", {}, include=lambda key: "")
    assert error.value.reason == "undefined-variable"
    with pytest.raises(PromptRenderError) as error:
        render_source("{{ _prompt_enter('x') }}", {}, include=lambda key: "")
    assert error.value.reason == "undefined-variable"


def test_render_uses_include_callback_for_nested_variables() -> None:
    sources = {
        "outer": "Dear {{ who }},\n{% include 'inner' %}",
        "inner": "— {{ who }}",
    }
    text = render_source(sources["outer"], {"who": "Ada"}, include=sources.__getitem__)
    assert text == "Dear Ada,\n— Ada"


def test_discovered_registration_reaches_the_singleton(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A discovered module's get_registry() must find the registry being built.

    The registration idiom is a module-level call at import time — which
    happens inside discovery, before the outer call has published anything.
    If the singleton is only assigned after the loop, the nested call builds
    a second registry, the registrations land there, and the outer call
    discards them: this test fails exactly that way.
    """
    package = tmp_path / "discovery_pkg"
    (package / "caps" / "discovered").mkdir(parents=True)
    for folder in (package, package / "caps", package / "caps" / "discovered"):
        (folder / "__init__.py").write_text("")
    (package / "caps" / "discovered" / "prompts.py").write_text(
        "from app.kernel.prompts import get_registry\n"
        "\n"
        "get_registry().register(\n"
        "    'discovered.key', template='x', sample_variables=lambda: {}\n"
        ")\n"
    )
    monkeypatch.setattr(sys, "path", [str(tmp_path), *sys.path])
    monkeypatch.setattr(prompts_registry, "_capabilities_dir", lambda: package / "caps")
    monkeypatch.setattr(prompts_registry, "_registry", None)
    registry = get_registry()
    assert registry.spec("discovered.key").key == "discovered.key"
    assert get_registry() is registry


def test_get_registry_idempotent_and_first_capability_docked() -> None:
    """The one registry, and the writing capability's bundled key rides in it.

    The "empty today" era ended when ``writing.continuation`` docked: the
    discovered module registers at import, so the singleton holds it — and
    stays the one instance across calls.
    """
    first = get_registry()
    assert get_registry() is first
    assert "writing.continuation" in first.keys()  # noqa: SIM118  the registry is no dict


def test_failed_discovery_does_not_publish_a_partial_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A build that raises rolls its publication back, so a retry rebuilds."""
    package = tmp_path / "rollback_pkg"
    (package / "caps" / "discovered").mkdir(parents=True)
    for folder in (package, package / "caps", package / "caps" / "discovered"):
        (folder / "__init__.py").write_text("")
    (package / "caps" / "discovered" / "prompts.py").write_text(
        "from app.kernel.prompts import get_registry\n"
        "\n"
        "get_registry().register(\n"
        "    'rollback.key', template='x', sample_variables=lambda: {}\n"
        ")\n"
    )

    def broken() -> Path:
        raise PermissionError("scan refused")

    monkeypatch.setattr(prompts_registry, "_registry", None)
    monkeypatch.setattr(prompts_registry, "_capabilities_dir", broken)
    with pytest.raises(PermissionError, match="scan refused"):
        get_registry()

    monkeypatch.setattr(prompts_registry, "_capabilities_dir", lambda: package / "caps")
    monkeypatch.setattr(sys, "path", [str(tmp_path), *sys.path])
    assert get_registry().spec("rollback.key").key == "rollback.key"


def test_missing_capabilities_directory_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No capabilities folder means an empty registry, not a crashed scan."""
    monkeypatch.setattr(prompts_registry, "_registry", None)
    monkeypatch.setattr(prompts_registry, "_capabilities_dir", lambda: tmp_path / "nowhere")
    assert get_registry().keys() == ()


def test_reason_vocabulary_exact() -> None:
    assert REASONS == (
        "syntax",
        "undefined-variable",
        "include-depth",
        "include-cycle",
        "include-missing",
        "forbidden",
        "runtime",
        "budget",
    )
