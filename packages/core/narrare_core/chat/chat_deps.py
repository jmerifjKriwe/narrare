"""Dependencies for ChatAgent.

ChatDeps provides the prompt composition infrastructure needed for
each chat turn. The PromptComposer and PromptContext are injected
by the service layer, keeping the agent pure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.prompts import PromptComposer
    from narrare_core.prompts.context import PromptContext


@dataclass
class ChatDeps:
    """Dependencies for ChatAgent.

    Provides the prompt composition infrastructure needed for
    each chat turn.

    Attributes:
        prompt_composer: Composer for assembling the full prompt cascade.
        context: Project context (language, genre, KB summaries, etc.).
        user_prompt: The user's current chat message.
    """

    prompt_composer: PromptComposer
    context: PromptContext
    user_prompt: str
