"""The prompt registry and the sandboxed render, pinned at the unit level.

The boundaries the kernel owns here: a spec round-trips through
``register``/``spec`` with its key set closed (duplicates refused, entry order
kept), and ``render_source`` returns the rendered text when every variable is
given — while each failure mode refuses with ``PromptRenderError`` and its
exact reason: an unknown ``{{ var }}`` is ``undefined-variable``, a broken
``{% %}`` is ``syntax``, a key already being rendered is ``include-cycle``,
and an include chain below the depth limit is ``include-depth``. The include
tracking must be a true render-time stack, not a seen-set: a diamond (two
sibling includes of one key) renders, and a chain of exactly five includes —
the limit — still renders. ``get_registry`` is the process-wide instance and,
today, empty: no capability ``prompts.py`` registers anything yet.
"""

import pytest

from app.kernel.prompts import (
    REASONS,
    PromptRegistry,
    PromptRenderError,
    get_registry,
    render_source,
)


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


def test_render_error_reasons_are_closed() -> None:
    with pytest.raises(ValueError, match="vocabulary"):
        PromptRenderError("crashed", "not a refusal")


def _chain_sources(links: int) -> dict[str, str]:
    """`k0` includes `k1` … `k{links}` ends in plain text: `links` includes deep."""
    return {
        f"k{i}": f"{{% include 'k{i + 1}' %}}" if i < links else "END" for i in range(links + 1)
    }


def test_render_include_cycle() -> None:
    sources = {"a": "{% include 'b' %}", "b": "{% include 'a' %}"}
    with pytest.raises(PromptRenderError) as error:
        render_source(sources["a"], {}, include=sources.__getitem__)
    assert error.value.reason == "include-cycle"
    assert error.value.detail


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


def test_render_uses_include_callback_for_nested_variables() -> None:
    sources = {
        "outer": "Dear {{ who }},\n{% include 'inner' %}",
        "inner": "— {{ who }}",
    }
    text = render_source(sources["outer"], {"who": "Ada"}, include=sources.__getitem__)
    assert text == "Dear Ada,\n— Ada"


def test_get_registry_idempotent_and_empty_today() -> None:
    first = get_registry()
    assert get_registry() is first
    assert first.keys() == ()


def test_reason_vocabulary_exact() -> None:
    assert REASONS == (
        "syntax",
        "undefined-variable",
        "include-depth",
        "include-cycle",
        "budget",
    )
