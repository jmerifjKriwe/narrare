"""The Hebel-2 stack cache resets its database between modules.

A cached stack (cache hit) must have its database reset so the next module
sees a clean database; a cache miss (fresh stack) must not call the reset
(because ``_start_capability_stack`` already prepares the database); and an
attached stack (``NARRE_E2E_ATTACH``) must never reset (the database belongs
to the artefact under test).
"""

from unittest import mock

import pytest

from app.kernel.testing import stack


@pytest.fixture(autouse=True)
def _clean_capability_cache():
    """Ensure a clean module-level cache for each test."""
    stack._CAPABILITY_STACKS.clear()  # pyright: ignore[reportPrivateUsage]
    yield
    stack._CAPABILITY_STACKS.clear()  # pyright: ignore[reportPrivateUsage]


def _fake_stack(
    database: str = "testdb", seed_user: bool = True, poll_return: object = None
) -> stack.Stack:
    """A Stack whose API process reports as alive (or dead if poll_return is set)."""
    proc = mock.MagicMock()
    proc.poll.return_value = poll_return
    return stack.Stack(
        environment={},
        api=proc,  # pyright: ignore[reportArgumentType]
        web=None,
        database=database,
        seed_user=seed_user,
    )


def test_a_cache_hit_resets_the_database(monkeypatch: pytest.MonkeyPatch) -> None:
    cached = _fake_stack(database="testdb", seed_user=True)
    stack._CAPABILITY_STACKS["cap"] = cached  # pyright: ignore[reportPrivateUsage]

    reset_mock = mock.MagicMock()
    monkeypatch.setattr(stack, "_reset_cached_stack", reset_mock)  # pyright: ignore[reportUnknownMemberType]
    start_mock = mock.MagicMock()
    monkeypatch.setattr(stack, "_start_capability_stack", start_mock)  # pyright: ignore[reportUnknownMemberType]

    result = stack.acquire_stack("cap", database="testdb", seed_user=True)

    assert result is cached
    reset_mock.assert_called_once_with("testdb", True)
    start_mock.assert_not_called()


def test_a_cache_miss_does_not_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_mock = mock.MagicMock()
    monkeypatch.setattr(stack, "_reset_cached_stack", reset_mock)  # pyright: ignore[reportUnknownMemberType]
    start_mock = mock.MagicMock(return_value=_fake_stack())
    monkeypatch.setattr(stack, "_start_capability_stack", start_mock)  # pyright: ignore[reportUnknownMemberType]

    stack.acquire_stack("cap", database="testdb", seed_user=True)

    reset_mock.assert_not_called()
    start_mock.assert_called_once()


def test_a_dead_cached_stack_is_replaced_without_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    dead = _fake_stack(poll_return=1)  # process exited
    stack._CAPABILITY_STACKS["cap"] = dead  # pyright: ignore[reportPrivateUsage]

    reset_mock = mock.MagicMock()
    monkeypatch.setattr(stack, "_reset_cached_stack", reset_mock)  # pyright: ignore[reportUnknownMemberType]
    start_mock = mock.MagicMock(return_value=_fake_stack())
    monkeypatch.setattr(stack, "_start_capability_stack", start_mock)  # pyright: ignore[reportUnknownMemberType]

    stack.acquire_stack("cap", database="testdb", seed_user=True)

    reset_mock.assert_not_called()
    start_mock.assert_called_once()


def test_attach_mode_never_resets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(stack, "ATTACH", True)  # pyright: ignore[reportUnknownMemberType]
    cached = _fake_stack(database="testdb", seed_user=True)
    stack._CAPABILITY_STACKS["cap"] = cached  # pyright: ignore[reportPrivateUsage]

    reset_mock = mock.MagicMock()
    monkeypatch.setattr(stack, "_reset_cached_stack", reset_mock)  # pyright: ignore[reportUnknownMemberType]

    stack.acquire_stack("cap", database="testdb", seed_user=True)

    reset_mock.assert_not_called()
