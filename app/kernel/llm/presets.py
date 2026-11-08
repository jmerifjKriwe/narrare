"""The provider presets: nine endpoints the create form fills in one click.

A preset is a form filler, never a resolution path — nothing at call time
reads this table, and every field it fills stays editable in the form. The
labels and models are the vendors' proper spellings: data, not catalog text.
``zai-coding-plan`` carries a note key because its endpoint answers only
under the Coding Plan's terms, and the form says so while that preset is
chosen. The vendor strings are the models.dev catalog's own prefixes, so
:func:`app.kernel.llm.catalog.vendor_models` fills each preset's picker from
the same snapshot the pricing reads.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPreset:
    """One provider template: the endpoint facts and a suggested model.

    ``models_url`` is ``None`` for the vendors whose base URL serves the
    model list itself (``{base_url}/models``); only the OpenCode inferences
    keep their list on a separate path. ``note_key`` names the one i18n
    string a preset may owe the form; ``None`` for the eight without terms
    to state.
    """

    id: str
    label: str
    kind: str
    base_url: str
    models_url: str | None
    vendor: str
    model: str
    note_key: str | None = None


PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset(
        "openai", "OpenAI", "openai-chat", "https://api.openai.com/v1", None, "openai", "gpt-5.4"
    ),
    ProviderPreset(
        "anthropic",
        "Claude",
        "anthropic",
        "https://api.anthropic.com/v1",
        None,
        "anthropic",
        "claude-sonnet-5-5",
    ),
    ProviderPreset("xai", "Grok", "openai-chat", "https://api.x.ai/v1", None, "xai", "grok-4.7"),
    ProviderPreset(
        "google",
        "Gemini",
        "openai-chat",
        "https://generativelanguage.googleapis.com/v1beta/openai",
        None,
        "google",
        "gemini-3.8-flash",
    ),
    ProviderPreset(
        "openrouter",
        "OpenRouter",
        "openai-chat",
        "https://openrouter.ai/api/v1",
        None,
        "openrouter",
        "z-ai/glm-5.3-flash",
    ),
    ProviderPreset(
        "opencode",
        "OpenCode",
        "openai-chat",
        "https://opencode.ai/inference/openai/v1",
        "https://opencode.ai/inference/v1/models",
        "opencode",
        "glm-5.3-flash",
    ),
    ProviderPreset(
        "opencode-go",
        "OpenCode Go",
        "openai-chat",
        "https://opencode.ai/inference/go/openai/v1",
        "https://opencode.ai/inference/go/v1/models",
        "opencode-go",
        "glm-5.3-flash",
    ),
    ProviderPreset(
        "zai", "Z.ai", "openai-chat", "https://api.z.ai/api/paas/v4", None, "zai", "glm-5.3"
    ),
    ProviderPreset(
        "zai-coding-plan",
        "Z.ai Coding Plan",
        "openai-chat",
        "https://api.z.ai/api/coding/paas/v4",
        None,
        "zai-coding-plan",
        "glm-5.3",
        "settings.providers.note.zaiCodingPlan",
    ),
)


def preset(preset_id: str) -> ProviderPreset | None:
    """The preset the id names, or ``None`` — the form's own lookup."""
    return next((entry for entry in PRESETS if entry.id == preset_id), None)
