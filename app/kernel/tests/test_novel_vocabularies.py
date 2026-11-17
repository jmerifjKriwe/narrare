"""The wizard's vocabularies: one home beside the novel contract (W4 §5).

Setup's request schema and writing's novel update validate against these
constants — the Stitch drafts' radio values, not a copy per door. The pin
is the PROVIDER_KINDS one: a drift in the set or the bounds fails here,
loudly, before either door can store a value the other would refuse.
"""

from app.kernel.contracts.models import (
    AI_ROLES,
    AUTHOR_TYPOLOGIES,
    CANON_STRICTNESS_MAX,
    CANON_STRICTNESS_MIN,
    DRAMATIC_FORM_MAX_LENGTH,
    WORD_GOAL_MAX,
    WORD_GOAL_MIN,
)


def test_the_wizard_vocabularies_are_the_drafts_radio_values() -> None:
    assert AUTHOR_TYPOLOGIES == ("plotter", "pantser", "plantser")
    assert AI_ROLES == ("archivar", "coautor", "lektor", "sparring")


def test_the_wizard_bounds_are_the_columns_own() -> None:
    # Canon strictness is the wizard's one-to-five track; the dramatic form
    # stays a free string whose width is the column's own (String(80)).
    assert (CANON_STRICTNESS_MIN, CANON_STRICTNESS_MAX) == (1, 5)
    assert DRAMATIC_FORM_MAX_LENGTH == 80
    # Every word goal counts from one; the ceiling is the Integer column's
    # own (2**31 - 1), refused at the gate, never an overflow at the write.
    assert (WORD_GOAL_MIN, WORD_GOAL_MAX) == (1, 2_147_483_647)
