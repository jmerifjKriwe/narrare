"""Startup validation, in one place, with one observable line.

Called once from the app's lifespan. Three silent failures it refuses: a
fallback to the fake providers that looks like a configured one, a vector width
that no longer matches the applied migration, and a real provider that is half
configured — that one would otherwise fail with the user's first prompt instead.
"""

from logging import getLogger
from os import environ

from app.kernel.embeddings import SCHEMA_DIMENSIONS, get_embedding_provider
from app.kernel.llm import get_provider


def validate_configuration() -> None:
    dimensions = int(environ.get("NARRE_EMBEDDING_DIMENSIONS", str(SCHEMA_DIMENSIONS)))
    if dimensions != SCHEMA_DIMENSIONS:
        raise RuntimeError(
            f"NARRE_EMBEDDING_DIMENSIONS={dimensions} does not match the applied schema"
            f" ({SCHEMA_DIMENSIONS}); changing the width needs a migration"
        )
    text = get_provider()
    embeddings = get_embedding_provider()
    for boundary, provider in (("llm", text), ("embedding", embeddings)):
        problems = provider.configuration_problems()
        if problems:
            raise RuntimeError(
                f"{boundary}={provider.describe()} is not configured: {'; '.join(problems)}"
            )
    getLogger("narrare").info(
        "providers llm=%s embedding=%s dimensions=%d",
        text.describe(),
        embeddings.describe(),
        dimensions,
    )
