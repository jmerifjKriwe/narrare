"""Unit tests for context/_render_options.py — RenderOptions (CR-AUFG-04-01).

RenderOptions is the per-invocation control that opts a KBContextEnvelope
renderer into provenance annotation. Default (``annotate_provenance=False``)
preserves current behaviour byte-for-byte.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from narrare_core.context._render_options import RenderOptions


class TestRenderOptionsDefaults:
    """RenderOptions default is the backward-compatible no-op."""

    def test_default_disables_annotation(self) -> None:
        opts = RenderOptions()
        assert opts.annotate_provenance is False

    def test_explicit_disabled_matches_default(self) -> None:
        assert RenderOptions(annotate_provenance=False) == RenderOptions()


class TestRenderOptionsImmutability:
    """RenderOptions is frozen + slotted (RULE-09, matches RenderedKBContext)."""

    def test_cannot_set_annotate_provenance(self) -> None:
        opts = RenderOptions()
        with pytest.raises(FrozenInstanceError):
            cast("Any", opts).annotate_provenance = True

    def test_cannot_add_attribute(self) -> None:
        """slots=True prevents adding new attributes."""
        opts = RenderOptions()
        with pytest.raises((AttributeError, TypeError)):
            cast("Any", opts).extra = "unexpected"

    def test_has_no_dict_attribute(self) -> None:
        opts = RenderOptions()
        assert not hasattr(opts, "__dict__")

    def test_is_hashable(self) -> None:
        """Frozen dataclass is hashable (usable as dict key / set member)."""
        a = RenderOptions(annotate_provenance=True)
        b = RenderOptions(annotate_provenance=True)
        assert hash(a) == hash(b)
        assert len({a, b, RenderOptions()}) == 2
