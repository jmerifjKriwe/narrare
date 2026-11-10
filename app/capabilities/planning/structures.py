"""The story structures the storyboard can lay chapters out in.

A structure tiles the unit interval with named stages; a chapter's position
ratio (its position over the last position, zero for a single chapter)
suggests the first stage whose range contains it, the shared boundary
belonging to the earlier stage. AI modes are deliberately out of this
slice: the suggestion is position-ratio only.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StageDef:
    """One storyboard column: the key stored on assignment, the i18n title
    key the canvas reads, and the half-open range of position ratios."""

    key: str
    title_key: str
    from_ratio: float
    to_ratio: float


def _even_stages(keys: list[str]) -> tuple[StageDef, ...]:
    """Contiguous stages tiling the unit interval, one share per key."""
    count = len(keys)
    return tuple(
        StageDef(
            key=key,
            title_key=f"storyboard.stage.{key}",
            from_ratio=index / count,
            to_ratio=(index + 1) / count,
        )
        for index, key in enumerate(keys)
    )


def _even_twelfths(keys: list[str]) -> tuple[StageDef, ...]:
    """Twelve contiguous stages, each one twelfth of the story."""
    assert len(keys) == 12
    return _even_stages(keys)


STRUCTURES: dict[str, tuple[StageDef, ...]] = {
    "three-act": (
        StageDef(key="setup", title_key="storyboard.stage.setup", from_ratio=0.0, to_ratio=0.25),
        StageDef(
            key="confrontation",
            title_key="storyboard.stage.confrontation",
            from_ratio=0.25,
            to_ratio=0.75,
        ),
        StageDef(
            key="resolution",
            title_key="storyboard.stage.resolution",
            from_ratio=0.75,
            to_ratio=1.0,
        ),
    ),
    "heros-journey": _even_twelfths(
        [
            "ordinary-world",
            "call-to-adventure",
            "refusal",
            "mentor",
            "threshold",
            "tests-allies-enemies",
            "approach",
            "ordeal",
            "reward",
            "road-back",
            "resurrection",
            "return",
        ]
    ),
    "save-the-cat": _even_stages(
        [
            "opening-image",
            "theme-stated",
            "set-up",
            "catalyst",
            "debate",
            "break-into-two",
            "b-story",
            "fun-and-games",
            "midpoint",
            "bad-guys-close-in",
            "all-is-lost",
            "dark-night-of-the-soul",
            "break-into-three",
            "finale",
            "final-image",
        ]
    ),
    "five-act": _even_stages(
        [
            "exposition",
            "rising-action",
            "climax",
            "falling-action",
            "resolution",
        ]
    ),
    "seven-point": _even_stages(
        [
            "hook",
            "plot-turn-1",
            "pinch-point-1",
            "midpoint",
            "pinch-point-2",
            "plot-turn-2",
            "resolution",
        ]
    ),
}
"""The backend registry, mirrored in UI copy. Every structure tiles [0, 1]
contiguously from zero, which is what makes the suggestion a first match."""

DEFAULT_STRUCTURE_ID = "three-act"
"""The structure a novel shows until the writer confirms a remap."""


def require_structure(structure_id: str) -> tuple[StageDef, ...]:
    """The structure's stages, or a refusal naming the unknown id."""
    try:
        return STRUCTURES[structure_id]
    except KeyError:
        raise UnknownStructureError(f"unknown structure: {structure_id}") from None


def suggest_stage(stages: tuple[StageDef, ...], ratio: float) -> StageDef:
    """The first stage whose range contains the ratio, the last when none
    does — a ratio of exactly one belongs to the final stage."""
    clamped = min(max(ratio, 0.0), 1.0)
    for stage in stages:
        if clamped <= stage.to_ratio:
            return stage
    return stages[-1]


class UnknownStructureError(ValueError):
    """The structure id names no registered structure."""
