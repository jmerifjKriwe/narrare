"""Normalize SceneBreak + DialogueMark to clean semantic equivalents.

Pure tree transforms — each function operates on a parsed BeautifulSoup tree
and mutates it in place. No string I/O.

Selectors are derived from the TipTap extension source:

- **SceneBreak** — ``SceneBreak.renderHTML``
  (``packages/web/.../extensions/SceneBreak.ts``) emits
  ``<p class="scene-break">* * *</p>``. The node's ``parseHTML`` also accepts
  ``<hr class="scene-break">`` (a round-trip fallback). Both forms are
  normalized to a single canonical ``<hr class="scene-break">``: the HTML
  semantic for a thematic break, tagged so the Typst ``narrare-roman`` renderer
  can replace it with an ornament (Slice 5f). The literal ``* * *`` text is
  dropped — the renderer owns the visual, the normalizer produces one stable
  representation.

- **DialogueMark** — ``DialogueMark.renderHTML``
  (``packages/web/.../extensions/DialogueMark.ts``) emits
  ``<span class="dialogue">…</span>`` wrapping quoted speech. The quotes
  themselves carry the dialogue semantics; the class is a styling hook that
  must not reach pandoc/Typst. The span is *unwrapped* — the inner quoted text
  is kept verbatim.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

#: Both SceneBreak forms (the emitted ``<p>`` and the round-trip ``<hr>``).
_SCENE_BREAK_SELECTOR = "p.scene-break, hr.scene-break"

#: DialogueMark span (see ``DialogueMark.parseHTML``).
_DIALOGUE_SELECTOR = "span.dialogue"


def normalize_scene_breaks(soup: BeautifulSoup) -> None:
    """Replace every scene-break form with the canonical ``<hr class="scene-break">``.

    A single grouped CSS query snapshots all scene-break nodes up front, so the
    freshly-created ``<hr>`` replacements are not re-selected during iteration.
    """
    for tag in soup.select(_SCENE_BREAK_SELECTOR):
        canonical = soup.new_tag("hr", attrs={"class": "scene-break"})
        tag.replace_with(canonical)


def normalize_dialogue(soup: BeautifulSoup) -> None:
    """Unwrap every ``<span class="dialogue">`` — keep the quoted text verbatim."""
    for tag in soup.select(_DIALOGUE_SELECTOR):
        tag.unwrap()
