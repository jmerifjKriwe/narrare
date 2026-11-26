"""The shared relation bound: one kernel constant, in the kernel's own tests.

Rule 1 keeps chat and knowledge from importing each other, so a bound both
enforce lives in the kernel and both import it — the allowed direction. Each
consumer's refusal is pinned in that capability's own tests (the create
endpoint in `app/capabilities/knowledge/tests/test_entity_create.py`, the
interview's normalisation in `app/capabilities/chat/tests/test_interviews.py`):
a kernel test importing `app.capabilities` would point against the
architecture's one-way dependencies. These tests pin the constant itself and
the re-export every consumer reads.
"""

from app.kernel.contracts import models
from app.kernel.contracts.knowledge import MAX_RELATIONS


def test_the_bound_is_twelve() -> None:
    assert MAX_RELATIONS == 12


def test_the_models_contract_exports_the_bounds_value() -> None:
    """The module the capabilities import carries the same value, so a copy
    set to another number cannot hide here; the use-site probes in each
    capability's suite are the real guard that they read it."""
    assert models.MAX_RELATIONS == MAX_RELATIONS
