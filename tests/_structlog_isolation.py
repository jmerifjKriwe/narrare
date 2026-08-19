"""Structlog global-state isolation — class-root anti-flake fixture.

MECHANISM (structlog 26.1.0, proven via ablation in commit 9ab76c1d):

* ``structlog.configure(processors=[...])`` REPLACES the configured
  processors-list object identity.
* ``structlog.testing.capture_logs()`` mutates only the CURRENT list in
  place (``clear()`` + ``extend()``, ``structlog/testing.py``) — a bound
  logger holding an OLDER list identity bypasses the capture.
* While ``cache_logger_on_first_use=True`` is active,
  ``BoundLoggerLazyProxy.bind`` pins the proxy on first use by assigning an
  INSTANCE ``bind`` attribute (``structlog/_config.py``) that closes over
  the then-current list. The pin survives any later ``configure()``.

POLLUTERS (tests that leave global structlog state mutated):

* Direct ``structlog.configure(...)``: ``test_logging.py`` (self-restoring
  since 9ab76c1d), ``test_ws_direction_dispatch_end_session.py``
  (self-restoring; identity-exact).
* Real ``configure_logging()`` via the FastAPI lifespan (``with
  TestClient(create_app(...))`` in the WS integration tests): leaks
  ``cache_logger_on_first_use=True``, a new processors-list identity, the
  stdlib logger factory/wrapper, cleared root handlers AND pinned
  production proxies — nothing restores it.

Depending on pytest-randomly order, a later ``capture_logs()`` test in the
same xdist worker then asserts on an empty capture list — ONE different
log-assertion test flakes per full run.

FIX (class root, not whack-a-mole): an autouse fixture in the ROOT
conftest isolates structlog config + root-logger state around EVERY test.
It is drift-gated (teardown no-ops unless the test actually mutated global
state) so the common path costs one ``get_config()`` plus one list copy
(microseconds). On drift it additionally unpins every module-reachable
lazy proxy: proxy pinning is only possible while
``cache_logger_on_first_use`` was True, which itself constitutes drift —
config restoration alone cannot undo pins created during the test.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

import pytest
import structlog

# structlog does not re-export BoundLoggerLazyProxy publicly (26.1.0); it is
# the documented return type of structlog.get_logger() and has lived in
# structlog._config (stable, unchanged semantics) since 2016.
from structlog._config import BoundLoggerLazyProxy

if TYPE_CHECKING:
    from collections.abc import Iterator


def _snapshot_structlog() -> dict[str, Any]:
    """Snapshot the global structlog config with a COPIED processors list.

    The list copy is load-bearing (9ab76c1d): ``capture_logs()`` mutates the
    configured list in place and ``configure()`` replaces its identity — a
    snapshot held by reference would be corrupted or stale. Processor
    instances stay shared by identity; only the list object is copied.
    """
    saved = structlog.get_config()
    saved["processors"] = list(saved["processors"])
    return saved


def _structlog_drifts(saved: dict[str, Any]) -> bool:
    """Return whether the current global config differs from the snapshot.

    Content comparison (not identity): a ``configure()`` that swaps the list
    identity for an equal-content list produces an equivalent state and does
    not need a restore.
    """
    current = structlog.get_config()
    return (
        current["processors"] != saved["processors"]
        or current["logger_factory"] is not saved["logger_factory"]
        or current["wrapper_class"] is not saved["wrapper_class"]
        or current["context_class"] is not saved["context_class"]
        or current["cache_logger_on_first_use"] != saved["cache_logger_on_first_use"]
    )


def _unpin_value(value: object) -> None:
    """Unpin one candidate value if it is a pinned lazy proxy (or a class
    whose attributes hold one)."""
    if isinstance(value, BoundLoggerLazyProxy):
        # structlog pins via ``self.bind = finalized_bind`` — an instance
        # attribute shadowing the class method. Removing it restores lazy
        # resolution through the CURRENT global config.
        value.__dict__.pop("bind", None)
    elif isinstance(value, type):
        for attr in tuple(vars(value).values()):
            if isinstance(attr, BoundLoggerLazyProxy):
                attr.__dict__.pop("bind", None)


def _unpin_cached_lazy_proxies() -> None:
    """Remove instance-level ``bind`` pinning from every reachable proxy.

    Scans module namespaces (and one level of class attributes) in
    ``sys.modules``. Tuple snapshots guard against concurrent mutation.
    Only runs on drift (polluter teardowns), so the sweep cost never lands
    on the common path.
    """
    for module in tuple(sys.modules.values()):
        if module is None:  # import-machinery placeholder
            continue
        for value in tuple(vars(module).values()):
            _unpin_value(value)


def _isolate_structlog_config_impl() -> Iterator[None]:
    """Isolate global structlog config + root-logger state around a test.

    See the module docstring for the flake mechanism and polluter classes.
    Plain generator (not fixture-decorated) so unit tests can drive it via
    the generator protocol; pytest 8 forbids calling fixtures directly.

    Teardown (drift-gated):

    1. unpin every reachable lazy proxy (pins can only be created while
       ``cache_logger_on_first_use=True`` was leaked — i.e. under drift),
    2. restore the structlog config snapshot,
    3. restore root-logger handlers/level — ``configure_logging()`` clears
       and re-installs them; leaked handlers (incl. a RotatingFileHandler
       on ``logs/error.log``) would otherwise keep receiving every later
       test's records, and a leaked root level could gate DEBUG records
       away from caplog.
    """
    saved_structlog = _snapshot_structlog()
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    yield
    if _structlog_drifts(saved_structlog):
        _unpin_cached_lazy_proxies()
        structlog.configure(**saved_structlog)
    if root.handlers != saved_handlers or root.level != saved_level:
        for handler in root.handlers[:]:
            if handler not in saved_handlers:
                handler.close()
                root.removeHandler(handler)
        for handler in saved_handlers:
            if handler not in root.handlers:
                root.addHandler(handler)
        root.setLevel(saved_level)


@pytest.fixture(autouse=True)
def _isolate_structlog_config() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """Autouse wrapper: isolate structlog + root-logger state around EVERY test."""
    yield from _isolate_structlog_config_impl()
