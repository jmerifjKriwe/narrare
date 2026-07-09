"""Deterministic CI-safe smoke task for the ``names`` suite.

Extracted as a standalone module (mirroring ``writing_prose_smoke.py`` /
``kb_operations_smoke.py``) and imported lazily by
``SmokeTaskFactory.names_task`` so ``evals/tasks/smoke.py`` stays within
the RULE-04 file-size limit. The ``names`` suite is smoke-only — there is
no runtime task and no provider is called.

The builder produces exactly ``inputs.count`` plausible names derived from
``name_type`` + ``seed_terms``: per-type template pools give the kind its
flavour, and when a seed term is present it is folded into the first name
(titled + a kind-noun) so the output visibly derives from the seed without
merely echoing it verbatim. Output is always non-empty, unique, and
non-echoing, so every evaluator scores ``1.0`` in smoke mode.
"""

from __future__ import annotations

from evals.models import NameGenerationInput, NameGenerationResult

# Per-type base-name pools. Each entry is a complete, plausible name of the
# corresponding kind; they are the deterministic smoke vocabulary.
_CHARACTER_POOL: tuple[str, ...] = (
    "Mara Silverwood",
    "Kael Driftwood",
    "Iven Marrow",
    "Sera Voss",
    "Bram Holloway",
    "Linn Ashford",
)
_PLACE_POOL: tuple[str, ...] = (
    "Greyfen Hollow",
    "Stormgate Reach",
    "Ashenmoor Vale",
    "Brackwater Fen",
    "Cinderfall Ridge",
    "Mistveil Cairn",
)
_PLOT_POOL: tuple[str, ...] = (
    "The Silverwood Betrayal",
    "The Hollow Crown's Reckoning",
    "The Driftwood Pact",
    "The Marrow Accord",
    "The Stormgate Siege",
    "The Ashenmoor Vigil",
)

_POOLS: dict[str, tuple[str, ...]] = {
    "character": _CHARACTER_POOL,
    "place": _PLACE_POOL,
    "plot": _PLOT_POOL,
}

# Kind-noun appended to a folded seed term so the derived name is a complete
# name of the right kind and never merely the seed verbatim.
_SEED_NOUN: dict[str, str] = {
    "character": "Scion",
    "place": "Hold",
    "plot": "Reckoning",
}

# Roman suffixes used only when ``count`` exceeds the pool size, to keep
# generated names unique. The numeric fallback covers any larger count.
_ROMAN_SUFFIXES: tuple[str, ...] = (
    "",
    "II",
    "III",
    "IV",
    "V",
    "VI",
    "VII",
    "VIII",
    "IX",
    "X",
    "XI",
    "XII",
)


async def names_task(inputs: object) -> object:
    """Run the CI-safe name-generation smoke task."""

    return await names(NameGenerationInput.model_validate(inputs))


async def names(inputs: NameGenerationInput) -> NameGenerationResult:
    """Produce deterministic, schema-valid name output without LLM calls."""

    return NameGenerationResult(
        names=_build_names(inputs),
        name_type=inputs.name_type,
        notes="Smoke name generation is deterministic — no model called.",
    )


def _build_names(inputs: NameGenerationInput) -> list[str]:
    """Build exactly ``inputs.count`` unique, non-empty, non-echoing names."""

    pool = _POOLS[inputs.name_type]
    count = max(1, inputs.count)
    seed = _clean_seed(inputs.seed_terms)

    names: list[str] = []
    index = 0
    while len(names) < count:
        cycle, offset = divmod(index, len(pool))
        name = pool[offset]
        if cycle:
            name = f"{name} {_roman_for(cycle)}"
        if index == 0 and seed:
            name = _fold_seed(seed, inputs.name_type)
        if name not in names:
            names.append(name)
        index += 1
    return names


def _clean_seed(seed_terms: list[str]) -> str:
    """Return the first non-empty seed term, title-cased, or empty string."""

    for term in seed_terms:
        stripped = term.strip()
        if stripped:
            return stripped.title()
    return ""


def _fold_seed(seed: str, name_type: str) -> str:
    """Combine a title-cased seed with a kind-noun into a derived name.

    The result is a complete name that visibly derives from the seed yet
    never equals it verbatim (e.g. ``"Silver Scion"``, ``"Iron Hold"``,
    ``"Crown Reckoning"``).
    """

    return f"{seed} {_SEED_NOUN[name_type]}"


def _roman_for(cycle: int) -> str:
    """Roman-numeral suffix for a 1-based cycle, with a numeric fallback."""

    if 0 < cycle < len(_ROMAN_SUFFIXES):
        return _ROMAN_SUFFIXES[cycle]
    return f"#{cycle + 1}"
