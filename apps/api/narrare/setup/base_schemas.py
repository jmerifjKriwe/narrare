"""Setup Wizard base Pydantic schemas — Enums and Steps 1-3."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Enums — extensible via adding values
# ---------------------------------------------------------------------------


class StoryStructure(StrEnum):
    THREE_ACT = "three_act"
    FIVE_ACT = "five_act"
    HEROS_JOURNEY = "heros_journey"
    SAVE_THE_CAT = "save_the_cat"
    SEVEN_POINT = "seven_point"


class StoryTone(StrEnum):
    # Values mirror packages/web/types/wizard.ts (StoryTone union) — RULE-17.
    # Core instructions live in packages/core/narrare_core/writing/_tone_data.py
    # (TONE_INSTRUCTIONS). Add a tone in all three places, never just one.
    BALANCED = "balanced"
    DRAMATIC = "dramatic"
    HUMOROUS = "humorous"
    SUSPENSEFUL = "suspenseful"
    CONTEMPLATIVE = "contemplative"
    ROMANTIC = "romantic"
    DARK = "dark"
    ADVENTUROUS = "adventurous"
    QUIET = "quiet"


class StarterContent(StrEnum):
    BLANK = "blank"
    DEMO_FANTASY = "demo_fantasy"
    DEMO_SCIFI = "demo_scifi"
    DEMO_GERMAN = "demo_german"
    IMPORT = "import"


class AIProvider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    GROQ = "groq"
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    ZAI = "zai"


# ---------------------------------------------------------------------------
# Step 1: Location
# ---------------------------------------------------------------------------


class Step1LocationRequest(BaseModel):
    project_name: str = Field(min_length=1, max_length=100)
    writing_language: str = Field(default="en", min_length=2, max_length=10)
    autosave_interval: int = Field(default=30, ge=0, le=3600)

    @field_validator("project_name")
    @classmethod
    def validate_project_name(cls, v: str) -> str:
        """Must be a valid directory name."""
        forbidden = set('/\\:*?"<>|')
        if any(c in forbidden for c in v):
            raise ValueError('Project name contains invalid characters: / \\ : * ? " < > |')
        if v.strip() != v:
            raise ValueError("Project name cannot start or end with whitespace")
        return v


class Step1LocationResponse(BaseModel):
    valid: bool
    project_name: str
    writing_language: str
    autosave_interval: int


# ---------------------------------------------------------------------------
# Step 2: Novel
# ---------------------------------------------------------------------------


class Step2NovelRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    author: str = Field(default="", max_length=200)
    genre: str = Field(default="", max_length=100)
    logline: str = Field(default="", max_length=500)
    story_structure: StoryStructure = StoryStructure.THREE_ACT
    tone: StoryTone = StoryTone.DRAMATIC


class Step2NovelResponse(BaseModel):
    valid: bool
    title: str


# ---------------------------------------------------------------------------
# Step 3: Starter content
# ---------------------------------------------------------------------------


class Step3StarterRequest(BaseModel):
    # starter == IMPORT creates an empty novel server-side; the frontend
    # commits imported files afterwards via POST /import/commit (ADR-091).
    starter: StarterContent = StarterContent.BLANK


class DemoProjectInfo(BaseModel):
    """Metadata about a bundled demo project — loaded from metadata.json."""

    id: StarterContent
    title: str
    writing_language: str
    genre: str
    chapter_count: int
    character_count: int
    word_count: int
    description: str
    # Fields for wizard prefill (from project_md in metadata.json)
    author: str = ""
    logline: str = ""
    pov: str = ""
    tags: list[str] = []


class DemoListResponse(BaseModel):
    """Response for listing available demo projects."""

    demos: list[DemoProjectInfo]


class Step3StarterResponse(BaseModel):
    valid: bool
    starter: StarterContent
    demo_info: DemoProjectInfo | None = None
