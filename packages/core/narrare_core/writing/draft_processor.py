"""Draft post-processor — cleans and normalises LLM-generated prose.

Handles:
1. LLM artifact removal (prefixed boilerplate, code fences, notes)
2. Markdown normalisation (blank lines, scene breaks)
3. Incomplete trailing sentence removal
4. Word-target enforcement with ±10% tolerance

Implements :class:`DraftProcessorProtocol` from contracts.py.
"""

from __future__ import annotations

import re

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

_ARTIFACT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"^Here(?:'s| is) (?:your |the )?(?:chapter |draft |text )?.*?:\s*",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(r"^```(?:markdown|md)?\s*$", re.MULTILINE),
    re.compile(r"^```\s*$", re.MULTILINE),
    re.compile(r"^\*\*(?:Note|Disclaimer|Warning):?\*\*:?.*$", re.MULTILINE),
    re.compile(
        r"^#{1,3}\s+(?:Chapter|Kapitel|Chapitre)\s+\d+.*$",
        re.MULTILINE,
    ),
]

# Multiple blank lines (3+) → single blank line
_MULTI_BLANK_RE = re.compile(r"\n{3,}")

# Scene break normalisation — ensures *** sits on its own line
_SCENE_BREAK_RE = re.compile(r"\n*\*{3}\n*")

# Terminal punctuation + closing quotes
_TERMINAL_CHARS = frozenset(".!?…\u201d\u201c'\"")


class DraftProcessor:
    """Post-processes generated text into clean, consistent prose.

    Implements :class:`DraftProcessorProtocol`.  All methods are pure
    functions — no I/O, no side-effects.
    """

    def process(
        self,
        text: str,
        *,
        word_target: int | None = None,
        is_partial: bool = False,
    ) -> str:
        """Clean and normalise generated text.

        Parameters
        ----------
        text:
            Raw LLM output to process.
        word_target:
            If set, truncate to roughly this word count (±10 %).
        is_partial:
            ``True`` for mid-stream fragments — disables trailing
            sentence cleanup.
        """
        if not text:
            return ""

        # 1. Strip LLM artifacts
        cleaned = self._strip_artifacts(text)

        # 2. Normalise markdown
        cleaned = self._normalise_markdown(cleaned)

        # 3. Remove incomplete trailing sentence (skip for partial)
        if not is_partial:
            cleaned = self._remove_incomplete_trailing(cleaned)

        # 4. Word-target enforcement
        if word_target is not None:
            cleaned = self._enforce_word_target(cleaned, word_target)

        return cleaned.strip()

    # ------------------------------------------------------------------
    # Step 1: Artifact stripping
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_artifacts(text: str) -> str:
        """Remove common LLM boilerplate prefixes and markers."""
        for pattern in _ARTIFACT_PATTERNS:
            text = pattern.sub("", text)
        return text

    # ------------------------------------------------------------------
    # Step 2: Markdown normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_markdown(text: str) -> str:
        """Normalise blank lines and scene-break markers."""
        text = _MULTI_BLANK_RE.sub("\n\n", text)
        text = _SCENE_BREAK_RE.sub("\n\n***\n\n", text)
        return text

    # ------------------------------------------------------------------
    # Step 3: Trailing sentence cleanup
    # ------------------------------------------------------------------

    @staticmethod
    def _remove_incomplete_trailing(text: str) -> str:
        """Remove an incomplete trailing sentence fragment.

        If the text does not end with terminal punctuation, walk
        backwards to find the last sentence boundary and truncate
        there.  Returns the original text unchanged when no boundary
        is found.
        """
        stripped = text.rstrip()
        if not stripped:
            return text

        # Already ends with terminal punctuation or closing quote
        if stripped[-1] in _TERMINAL_CHARS:
            return text

        # Walk backwards for the last sentence-ending punctuation
        for i in range(len(stripped) - 1, -1, -1):
            if stripped[i] in ".!?…":
                # Include any closing quotes that follow
                end = i + 1
                while end < len(stripped) and stripped[end] in "\"'\u201d":
                    end += 1
                return text[:end].rstrip()

        # No sentence boundary found — return as-is
        return text

    # ------------------------------------------------------------------
    # Step 4: Word-target enforcement
    # ------------------------------------------------------------------

    @staticmethod
    def _enforce_word_target(text: str, word_target: int) -> str:
        """Truncate to nearest sentence boundary within ±10 % tolerance.

        When the text exceeds ``word_target * 1.10``, truncate at the
        last complete sentence that keeps the word count at or above
        ``word_target * 0.90``.
        """
        words = text.split()
        word_count = len(words)

        max_words = int(word_target * 1.10)
        min_words = int(word_target * 0.90)

        if word_count <= max_words:
            return text  # Already within tolerance

        # Truncate at word boundary, then find last sentence end
        truncated = " ".join(words[:max_words])

        # Scan backwards for last terminal punctuation
        last_end = -1
        for i in range(len(truncated) - 1, -1, -1):
            if truncated[i] in ".!?…":
                end = i + 1
                while end < len(truncated) and truncated[end] in "\"'\u201d":
                    end += 1
                last_end = end
                break

        if last_end > 0:
            result = truncated[:last_end]
            if len(result.split()) >= min_words:
                return result

        # Cannot truncate without going below minimum — return original
        return text
