"""Regression tests for multilingual PROMPT-QUALITY patterns.

Ensures the architecture checker at
``scripts/architecture/_checkers/prompt_quality.py`` correctly recognises
role assignments, output format specs, and Do-NOT rules in EN/DE/FR
bundled prompts, and correctly excludes fragment files (tones,
name-styles) from content quality checks.

All tests are pure unit tests: no LLM, no DB, no network.
"""

from __future__ import annotations

from scripts.architecture._checkers.prompt_quality import check_prompt_content_quality


class TestPromptContentQualityMultilingual:
    """Verify the architecture checker recognizes multilingual patterns."""

    def test_fragments_not_checked(self) -> None:
        """Files without prompt_type frontmatter should be excluded from PROMPT-QUALITY."""
        # Simulate a tone fragment file
        fragment_lines = [
            "---",
            "tone_id: dark",
            'tone_version: "1.0.0"',
            "---",
            "",
            "Use grim imagery and foreboding atmosphere.",
        ]
        result = check_prompt_content_quality(
            "prompts/_bundled/writing/tones/dark.md", fragment_lines
        )
        assert result == [], f"Fragment should produce no findings, got {result}"

    def test_de_role_recognized(self) -> None:
        """German role assignment 'Du bist' should be recognized."""
        prompt_lines = [
            "---",
            "prompt_type: writing",
            "prompt_language: de",
            'prompt_version: "1.0.0"',
            "---",
            "",
            "Du bist ein erfahrener Schreibassistent.",
            "",
            "### Ausgabeformat",
            "",
            "Gib ein JSON-Objekt zurück.",
            "",
            "- Erfinde NICHT neue Charaktere.",
            "- Widersprich NICHT etablierten Fakten.",
            "- Vermeide generische Platzhalter.",
        ]
        result = check_prompt_content_quality(
            "prompts/_bundled/writing/de/test/system.md", prompt_lines
        )
        assert result == [], f"DE prompt with all patterns should pass, got {result}"

    def test_fr_role_recognized(self) -> None:
        """French role assignment 'Tu es' should be recognized."""
        prompt_lines = [
            "---",
            "prompt_type: kb",
            "prompt_language: fr",
            'prompt_version: "1.0.0"',
            "---",
            "",
            "Tu es un assistant de la base de connaissances.",
            "",
            "### Format de sortie",
            "",
            "Renvoie un objet JSON.",
            "",
            "- N'invente PAS de noms d'entités.",
            "- N'extrais PAS d'entités sans informations.",
            "- Ne jamais inventer du texte source.",
        ]
        result = check_prompt_content_quality("prompts/_bundled/kb/fr/test/system.md", prompt_lines)
        assert result == [], f"FR prompt with all patterns should pass, got {result}"

    def test_en_missing_do_not_still_caught(self) -> None:
        """EN prompt with fewer than 3 Do-NOT rules should still be flagged."""
        prompt_lines = [
            "---",
            "prompt_type: analysis",
            "prompt_language: en",
            'prompt_version: "1.0.0"',
            "---",
            "",
            "You are a skilled analyst.",
            "",
            "### Output Format",
            "",
            "Return a JSON object.",
            "",
            "- Do not invent information.",
        ]
        result = check_prompt_content_quality(
            "prompts/_bundled/analysis/en/test/system.md", prompt_lines
        )
        # Should have exactly 1 finding: Do-NOT has only 1 rule
        assert len(result) == 1, f"Expected 1 finding (Do-NOT < 3), got {len(result)}: {result}"
        assert "Do-NOT" in result[0].detail

    def test_meta_prompt_exemptions(self) -> None:
        """Meta-prompts should not require output format; lite should not require role."""
        # Meta prompt — should NOT flag output format
        meta_lines = [
            "---",
            "prompt_type: meta",
            "prompt_language: en",
            'prompt_version: "2.2.0"',
            "---",
            "",
            "You are Narrare, a creative writing companion.",
            "",
            "- Do not ignore author preferences.",
            "- Do not refuse fiction content unless harmful.",
            "- Do not add meta-commentary.",
        ]
        result = check_prompt_content_quality("prompts/_bundled/meta/en/system.md", meta_lines)
        assert result == [], f"Meta prompt should pass (output format exempt), got {result}"

    def test_lite_prompt_role_exempt(self) -> None:
        """system.lite.md should not require role assignment."""
        lite_lines = [
            "---",
            "prompt_type: meta",
            "prompt_language: en",
            'prompt_version: "2.2.0"',
            "---",
            "",
            "Compact behavioral instructions for token-limited contexts.",
            "",
            "- Do not ignore outline.",
            "- Do not refuse fiction content unless harmful.",
            "- Do not add meta-commentary.",
        ]
        result = check_prompt_content_quality("prompts/_bundled/meta/en/system.lite.md", lite_lines)
        assert result == [], f"Lite prompt should pass (role exempt), got {result}"
