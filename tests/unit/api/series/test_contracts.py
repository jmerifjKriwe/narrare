"""Smoke test: Protocols are importable and have expected method signatures."""

from narrare.series.contracts import (
    SeriesRepositoryProtocol,
    SeriesServiceProtocol,
)
from narrare.series.join_contracts import SeriesJoinServiceProtocol


def test_series_repository_protocol_methods():
    methods = {
        "create",
        "get",
        "list_for_user",
        "update",
        "delete",
        "list_novels",
        "reorder_novels",
        "get_settings",
        "update_settings",
    }
    actual = set(dir(SeriesRepositoryProtocol))
    assert methods.issubset(actual)


def test_series_service_protocol_methods():
    methods = {
        "create_series",
        "get_series",
        "list_series",
        "update_series",
        "delete_series",
    }
    actual = set(dir(SeriesServiceProtocol))
    assert methods.issubset(actual)


def test_series_join_service_protocol_methods():
    methods = {"preview_join", "apply_join"}
    actual = set(dir(SeriesJoinServiceProtocol))
    assert methods.issubset(actual)
