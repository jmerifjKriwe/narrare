"""Strip editor-only artifacts (AIAnnotation mark + GhostText decorations).

Pure tree transforms — each function operates on a parsed BeautifulSoup tree
and mutates it in place. No string I/O.

Selectors are derived from the TipTap extension source:

- **AIAnnotation** — ``AIAnnotationMark.renderHTML`` / ``parseHTML``
  (``packages/web/components/studio/editor/extensions/AIAnnotation.ts``). The
  mark renders ``<span data-ai-generated="true" …>INNER</span>`` (plus
  ``data-request-id`` / ``data-source`` / ``data-original-text`` /
  ``data-status`` / ``data-created-at`` and ``class="ai-generated-text
  ai-generated-{status}"``). It wraps AI-generated text. The accepted edit
  becomes plain prose, so the wrapper is *unwrapped* — the inner content is
  kept, the wrapper and its metadata attributes are dropped.

- **GhostText** — a *decoration-based* extension
  (``packages/web/.../extensions/GhostText.ts``). It renders via ProseMirror
  ``Decoration.widget()``, so ``editor.getHTML()`` does **not** serialize it —
  it never reaches the normalizer in normal operation. The four decoration
  classes are ``ghost-text-suggestion`` / ``ghost-text-hint`` /
  ``ghost-text-fetching`` / ``ghost-text-error``. Any residue is stripped
  defensively: removed *entirely* (not unwrapped), because a suggestion that
  was never accepted is not manuscript content.

  Note: there is **no** ``data-ghost-text`` attribute (the extension never
  emits one); the decoration is identified solely by its ``ghost-text-*``
  class token.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

#: AIAnnotation mark wrapper (see ``AIAnnotationMark.parseHTML``).
_AI_ANNOTATION_SELECTOR = "span[data-ai-generated]"

#: GhostText decoration residue — any element whose class attribute contains a
#: ``ghost-text`` token. Matches all four decoration classes defensively.
_GHOST_TEXT_SELECTOR = '[class*="ghost-text"]'


def strip_ai_annotation(soup: BeautifulSoup) -> None:
    """Unwrap every ``<span data-ai-generated>`` — keep the inner text.

    The accepted AI edit becomes plain prose; the wrapper and its tracking
    attributes (request id, source, original text, status, timestamp) are
    discarded.
    """
    for tag in soup.select(_AI_ANNOTATION_SELECTOR):
        tag.unwrap()


def strip_ghost_text(soup: BeautifulSoup) -> None:
    """Remove any GhostText decoration residue entirely (defensive).

    GhostText is decoration-based and is not serialized by ``editor.getHTML()``,
    so under normal operation this is a no-op. If residue ever reaches the
    normalizer it is removed completely (not unwrapped): an unaccepted
    suggestion is not manuscript content.
    """
    for tag in soup.select(_GHOST_TEXT_SELECTOR):
        tag.decompose()
