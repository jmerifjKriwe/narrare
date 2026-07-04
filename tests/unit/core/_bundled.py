"""Package-relative resolver for bundled prompt assets (tests).

Mirrors production: narrare_core.prompts.registry.PromptRegistry._find_bundled_root.
Resolving bundled prompts via importlib.resources — NOT repo-root-relative
``Path(__file__).parents[N] / "packages/..."`` — keeps tests compatible with the
MutMut copy-based sandbox, where the instrumented package lives at
``mutants/narrare_core/`` and no ``mutants/packages/`` mirror exists.

In normal dev/CI runs this resolves to the same on-disk files as before, so test
behaviour is unchanged; only the resolution mechanism becomes package-relative.
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path

_PKG = "narrare_core"


def bundled_prompts_root() -> Path:
    """Absolute filesystem path to ``narrare_core/prompts/_bundled`` (package-resolved)."""
    ref = importlib.resources.files(_PKG) / "prompts" / "_bundled"
    return Path(str(ref))
