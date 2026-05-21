"""Schema validation tests for name generation — verify renamed fields."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from narrare.generation.schemas import NameGenerateRequest


class TestNameGenerateRequestFields:
    """Verify the renamed fields work and old field names are rejected."""

    def test_old_culture_field_ignored(self) -> None:
        """The 'culture' field is no longer recognized — it's silently ignored."""
        req = NameGenerateRequest(project_id=uuid4(), culture="fantasy")  # type: ignore[call-arg]
        assert req.name_style == "fantasy"  # falls back to default, culture ignored

    def test_old_language_field_ignored(self) -> None:
        """The 'language' field is no longer recognized — it's silently ignored."""
        req = NameGenerateRequest(project_id=uuid4(), language="en")  # type: ignore[call-arg]
        assert req.explanation_language == "en"  # falls back to default, language ignored

    def test_name_style_field_accepted(self) -> None:
        req = NameGenerateRequest(project_id=uuid4(), name_style="Nordisch")
        assert req.name_style == "Nordisch"

    def test_explanation_language_field_accepted(self) -> None:
        req = NameGenerateRequest(project_id=uuid4(), explanation_language="Deutsch")
        assert req.explanation_language == "Deutsch"

    def test_default_name_style_is_fantasy(self) -> None:
        req = NameGenerateRequest(project_id=uuid4())
        assert req.name_style == "fantasy"

    def test_default_explanation_language_is_en(self) -> None:
        req = NameGenerateRequest(project_id=uuid4())
        assert req.explanation_language == "en"

    def test_name_style_max_length_100(self) -> None:
        long_name = "x" * 101
        with pytest.raises(ValidationError):
            NameGenerateRequest(project_id=uuid4(), name_style=long_name)

    def test_name_style_max_length_100_accepted(self) -> None:
        exact_name = "x" * 100
        req = NameGenerateRequest(project_id=uuid4(), name_style=exact_name)
        assert len(req.name_style) == 100

    def test_explanation_language_max_length_50(self) -> None:
        long_lang = "x" * 51
        with pytest.raises(ValidationError):
            NameGenerateRequest(project_id=uuid4(), explanation_language=long_lang)

    def test_explanation_language_min_length_2(self) -> None:
        with pytest.raises(ValidationError):
            NameGenerateRequest(project_id=uuid4(), explanation_language="e")
