"""Startup validation, in one place, with one observable line.

Called once from the app's lifespan. The silent failure it refuses: a fallback
to a fake provider that looks like a configured one, or a real provider that is
half configured — that one would otherwise fail with the user's first prompt
instead. The vector width is not validated here because nothing fixes it: the
column accepts any width, and the corpus guard refuses a model switch at the
moment it happens.
"""

from logging import getLogger

from app.kernel.embeddings import get_embedding_provider
from app.kernel.llm import get_provider


def validate_configuration() -> None:
    text = get_provider()
    embeddings = get_embedding_provider()
    for boundary, provider in (("llm", text), ("embedding", embeddings)):
        problems = provider.configuration_problems()
        if problems:
            raise RuntimeError(
                f"{boundary}={provider.describe()} is not configured: {'; '.join(problems)}"
            )
    getLogger("narrare").info(
        "providers llm=%s embedding=%s",
        text.describe(),
        embeddings.describe(),
    )
