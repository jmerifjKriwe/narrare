"""Placeholder package test — proves the benchmark area is importable (Task 1).

Trivial by design: registration is the feature under test, not behavior.
"""

import benchmark


def test_package_importable_with_version() -> None:
    """The benchmark package must be importable and carry a version."""
    assert benchmark.__version__ == "0.1.0"
