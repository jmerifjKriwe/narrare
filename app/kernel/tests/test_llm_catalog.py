"""The vendored models.dev catalog: lookup, and what a call costs.

The cost truth table is design D4: a local endpoint is free whatever the
catalog knows, an unknown price is NULL — never 0 — and a priced remote call
is the Mtok sum at write time. The lookup cascade runs exact id → provider
prefix → normalized, first tier wins, and the profile's two columns override
the catalog's. The synthetic snapshots here pin the rules; the smoke tests
hold the vendored file to the shape the rules assume.
"""

from json import loads
from typing import TYPE_CHECKING

import pytest

from app.kernel.llm import catalog
from app.kernel.llm.catalog import ModelInfo, compute_cost, effective_info, load_catalog

if TYPE_CHECKING:
    from collections.abc import Callable

    # What the vendoring fixture installs: the snapshot effective_info reads.
    Install = Callable[[dict[str, ModelInfo]], None]

REMOTE = "https://api.vendor.example/v1"
LOCAL = "http://127.0.0.1:11434/v1"


def priced(input_price: float | None = 3.0, output_price: float | None = 15.0) -> ModelInfo:
    """A catalog entry whose price fields are the given ones, the rest fixed."""
    return ModelInfo(
        context_window=100_000,
        max_output_tokens=4_096,
        input_price_per_mtok=input_price,
        output_price_per_mtok=output_price,
        supports_json_schema=True,
        supports_tools=True,
        supports_vision=False,
    )


@pytest.fixture
def vendoring(monkeypatch: pytest.MonkeyPatch) -> Install:
    """Install a synthetic snapshot as the one effective_info reads."""

    def install(entries: dict[str, ModelInfo]) -> None:
        monkeypatch.setattr(catalog, "load_catalog", lambda: entries)

    return install


# The cost truth table.


def test_a_priced_remote_call_costs_the_mtok_sum(vendoring: Install) -> None:
    """Verify a priced model with full tokens sums both prices per million."""
    vendoring({"acme/turbo-3": priced()})
    info = effective_info(
        "acme/turbo-3", profile_context_window=None, profile_max_output_tokens=None
    )
    assert info == priced()
    cost = compute_cost(info, input_tokens=1_000, output_tokens=2_000, base_url=REMOTE)
    assert cost == pytest.approx(0.033)  # 1 000 * 3.0 + 2 000 * 15.0, per million


def test_an_unknown_model_on_a_remote_endpoint_costs_null(vendoring: Install) -> None:
    """Verify a model no tier reaches leaves the price unknown, not free."""
    vendoring({"acme/turbo-3": priced()})
    info = effective_info(
        "nope/unknown", profile_context_window=None, profile_max_output_tokens=None
    )
    assert info is None
    cost = compute_cost(info, input_tokens=1_000, output_tokens=2_000, base_url=REMOTE)
    assert cost is None


def test_a_priced_model_on_a_local_endpoint_is_free() -> None:
    """Verify locality beats the catalog's price: the loopback endpoint is free."""
    cost = compute_cost(priced(), input_tokens=1_000, output_tokens=2_000, base_url=LOCAL)
    assert cost == 0.0


def test_an_unknown_model_on_a_local_endpoint_is_still_free() -> None:
    """Verify the local tier comes first: even no info and no tokens are free."""
    cost = compute_cost(None, input_tokens=None, output_tokens=None, base_url=LOCAL)
    assert cost == 0.0


def test_missing_tokens_leave_the_cost_null() -> None:
    """Verify a call the provider did not report usage for stays unpriced."""
    no_input = compute_cost(priced(), input_tokens=None, output_tokens=2_000, base_url=REMOTE)
    no_output = compute_cost(priced(), input_tokens=1_000, output_tokens=None, base_url=REMOTE)
    assert (no_input, no_output) == (None, None)


def test_missing_prices_leave_the_cost_null() -> None:
    """Verify a catalog entry without both prices cannot price a call."""
    no_input = compute_cost(
        priced(input_price=None), input_tokens=1, output_tokens=1, base_url=REMOTE
    )
    no_output = compute_cost(
        priced(output_price=None), input_tokens=1, output_tokens=1, base_url=REMOTE
    )
    assert (no_input, no_output) == (None, None)


def test_an_absent_base_url_prices_as_remote() -> None:
    """Verify a caller with no endpoint to name is not local by that absence."""
    cost = compute_cost(priced(), input_tokens=1_000, output_tokens=2_000, base_url=None)
    assert cost == pytest.approx(0.033)


# The lookup cascade: exact → provider prefix → normalized, first tier wins.


def test_an_exact_id_wins_over_a_prefix_match(vendoring: Install) -> None:
    """Verify the exact full id is taken even when a prefix tier also reaches."""
    zed = priced(30.0, 60.0)
    vendoring({"aaa/turbo-3": priced(), "zed/turbo-3": zed})
    info = effective_info(
        "zed/turbo-3", profile_context_window=None, profile_max_output_tokens=None
    )
    assert info is zed  # not the first vendor in sort order, aaa/turbo-3


def test_a_prefix_match_wins_over_a_normalized_match(vendoring: Install) -> None:
    """Verify the vendor-swapped tier is taken before separator folding."""
    normalized = priced(120.0, 240.0)
    zed = priced(30.0, 60.0)
    vendoring({"aaa/TURBO.3": normalized, "zed/turbo-3": zed})
    info = effective_info("turbo-3", profile_context_window=None, profile_max_output_tokens=None)
    assert info is zed  # the normalized tier would have reached aaa/TURBO.3


def test_a_bare_model_id_matches_deterministically(vendoring: Install) -> None:
    """Verify a bare id takes the first full id in sort order under any vendor."""
    first = priced()
    vendoring({"aaa/turbo-3": first, "zzz/turbo-3": priced(30.0, 60.0)})
    info = effective_info("turbo-3", profile_context_window=None, profile_max_output_tokens=None)
    assert info is first


def test_a_vendor_prefix_is_traded_for_the_catalogs(vendoring: Install) -> None:
    """Verify a query's vendor segment is swapped, not matched: any full id's."""
    meta = priced()
    vendoring({"meta/llama-3": meta})
    info = effective_info(
        "groq/llama-3", profile_context_window=None, profile_max_output_tokens=None
    )
    assert info is meta


def test_a_normalized_match_folds_case_and_separators(vendoring: Install) -> None:
    """Verify `-` `.` `:` `_` and case fold away when nothing else matched."""
    meta = priced()
    eight_b = priced(0.5, 1.5)
    vendoring({"meta/llama-3": meta, "meta/llama-3-8b": eight_b})
    for model_id, expected in (("LLAMA.3", meta), ("llama3:8b", eight_b)):
        info = effective_info(model_id, profile_context_window=None, profile_max_output_tokens=None)
        assert info is expected


def test_an_id_no_tier_reaches_has_no_info(vendoring: Install) -> None:
    """Verify an unknown model is None even when the profile pinned windows."""
    vendoring({"meta/llama-3": priced()})
    info = effective_info(
        "totally-unknown", profile_context_window=8_192, profile_max_output_tokens=512
    )
    assert info is None


def test_profile_columns_override_the_catalogs_tunables(vendoring: Install) -> None:
    """Verify the profile's window columns win; prices stay the catalog's."""
    vendoring({"acme/turbo-3": priced()})
    both = effective_info(
        "acme/turbo-3", profile_context_window=8_192, profile_max_output_tokens=512
    )
    assert both is not None
    assert (both.context_window, both.max_output_tokens) == (8_192, 512)
    assert (both.input_price_per_mtok, both.output_price_per_mtok) == (3.0, 15.0)
    one = effective_info(
        "acme/turbo-3", profile_context_window=8_192, profile_max_output_tokens=None
    )
    assert one is not None
    assert (one.context_window, one.max_output_tokens) == (8_192, 4_096)


# The vendored snapshot itself.


def test_the_snapshot_parses_into_infos_keyed_by_full_ids() -> None:
    """Verify the vendored file loads, every id carrying its vendor segment."""
    entries = load_catalog()
    assert entries
    assert all(isinstance(info, ModelInfo) for info in entries.values())
    assert all("/" in model_id for model_id in entries)


def test_the_snapshot_carries_a_date_and_at_least_one_price() -> None:
    """Verify the snapshot names its date and holds a priced model to cost."""
    raw = loads(catalog.SNAPSHOT.read_text())
    assert isinstance(raw["snapshot_date"], str)
    assert any(
        info.input_price_per_mtok is not None and info.output_price_per_mtok is not None
        for info in load_catalog().values()
    )


def test_the_snapshot_is_parsed_once_per_process() -> None:
    """Verify the catalog is cached: the second read returns the first's own object.

    The resolver and the audit look the catalog up per call, and the snapshot
    is 2.5 MB of static JSON — re-parsing it per call would price every row
    with a file read.
    """
    assert load_catalog() is load_catalog()
