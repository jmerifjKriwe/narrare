"""The vendored models.dev catalog: one fact sheet per model id.

``data/models.json`` is a snapshot of ``https://models.dev/api.json`` reduced
to the fields this kernel needs, dated in ``snapshot_date`` and refreshed by
hand (:mod:`app.kernel.llm.data.refresh`) — nothing here touches the network
at runtime. Lookup tolerates how a profile spells a model, and the cost truth
table (design D4) turns what the catalog knows into what a call cost.

The snapshot is parsed once per process into a module cache and returned as a
read-only view, so a damaged file is a :class:`CatalogError` naming the file
at load instead of a bare ``KeyError`` at the first call it prices, and no
caller can leak a mutation into later lookups. Its two lookup indexes — the
vendor-prefix tier and the normalized tier — are built in the same pass, so a
lookup never re-sorts the thousands of ids.
"""

from collections.abc import Mapping  # noqa: TC003
from dataclasses import dataclass, replace
from json import loads
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import httpx

from app.kernel.vendor import LOCAL_HOSTS

SNAPSHOT = Path(__file__).parent / "data" / "models.json"

# The separators one vendor or another spells a model id with; the normalized
# tier folds them away (with case) so spelling cannot hide a known model.
_SEPARATORS = str.maketrans("", "", "-.:_")


class CatalogError(RuntimeError):
    """The vendored snapshot is damaged and cannot serve lookups.

    ``load_catalog`` raises it instead of letting the JSON's own ``KeyError``
    or ``TypeError`` escape: the message names the file, so a bad manual
    refresh is a readable failure at load, not a mystery at the first call
    it prices.
    """


@dataclass(frozen=True)
class ModelInfo:
    """What the catalog knows about one model id."""

    context_window: int | None
    max_output_tokens: int | None
    input_price_per_mtok: float | None
    output_price_per_mtok: float | None
    supports_json_schema: bool
    supports_tools: bool
    supports_vision: bool


_WINDOW_FIELDS = ("context_window", "max_output_tokens")
_PRICE_FIELDS = ("input_price_per_mtok", "output_price_per_mtok")
_FLAG_FIELDS = ("supports_json_schema", "supports_tools", "supports_vision")
_FIELDS = _WINDOW_FIELDS + _PRICE_FIELDS + _FLAG_FIELDS
"""The exact entry shape ``ModelInfo`` carries: the snapshot's own."""

_catalog: MappingProxyType[str, ModelInfo] | None = None
"""The parsed snapshot, parsed once, then served by reference."""

_index_cache: dict[
    int, tuple[Mapping[str, ModelInfo], dict[str, ModelInfo], dict[str, ModelInfo]]
] = {}
"""The lookup indexes per catalog mapping, keyed by the mapping's identity.

For the process's own snapshot there is exactly one mapping, so its indexes
are built exactly once. Tests install synthetic catalogs by monkeypatching
``load_catalog`` (the seam ``effective_info`` reads through); each installed
mapping is indexed on its first lookup, and every entry anchors its own
mapping — a freed test dict cannot have its id reused into a stale hit.
"""


def load_catalog() -> MappingProxyType[str, ModelInfo]:
    """Every vendored model, keyed by its full ``vendor/model`` id.

    Parsed once per process: the snapshot is static and 2.5 MB, and the
    resolver's per-call lookups must not re-read it. The return is a
    read-only view over the cached dict — an assignment raises ``TypeError``
    instead of leaking into every later lookup. A damaged snapshot — broken
    JSON, no ``models`` object, an entry whose fields are not exactly
    ``ModelInfo``'s, a value of the wrong kind — raises
    :class:`CatalogError` naming the file, at load.

    Tests that need their own snapshot monkeypatch this function; whatever
    mapping it returns is indexed like the real one, once per mapping.
    """
    global _catalog
    if _catalog is None:
        _catalog = MappingProxyType(_parse(SNAPSHOT))
    return _catalog


def _parse(snapshot: Path) -> dict[str, ModelInfo]:
    """Parse and shape-check the snapshot, or raise :class:`CatalogError`."""
    try:
        payload = loads(snapshot.read_text())
        entries = payload["models"]
        infos = {model_id: _info(model_id, entry) for model_id, entry in entries.items()}
    except (KeyError, TypeError, AttributeError, ValueError) as damaged:
        raise CatalogError(f"damaged catalog snapshot at {snapshot}: {damaged}") from damaged
    return infos


def _info(model_id: str, entry: object) -> ModelInfo:
    """One checked entry; a ``ValueError`` names the model and the flaw.

    The field set is exact — a misspelled or missing field from a bad manual
    refresh is damage, not a default — and every value must fit its column's
    kind: ``None`` or an integer for the windows, ``None`` or a number for
    the prices, a boolean for the capability flags.
    """
    if not isinstance(entry, dict):
        raise ValueError(f"model {model_id}: entry is not an object")
    fields = cast("dict[str, Any]", entry)  # shape-checked below, then trusted
    if set(fields) != set(_FIELDS):
        raise ValueError(
            f"model {model_id}: fields {sorted(fields)} are not exactly {sorted(_FIELDS)}"
        )
    for field in _WINDOW_FIELDS:
        if fields[field] is not None and not isinstance(fields[field], int):
            raise ValueError(f"model {model_id}: {field} is not an integer or null")
    for field in _PRICE_FIELDS:
        if fields[field] is not None and not isinstance(fields[field], int | float):
            raise ValueError(f"model {model_id}: {field} is not a number or null")
    for field in _FLAG_FIELDS:
        if not isinstance(fields[field], bool):
            raise ValueError(f"model {model_id}: {field} is not a boolean")
    return ModelInfo(**fields)


def effective_info(
    model_id: str,
    *,
    profile_context_window: int | None,
    profile_max_output_tokens: int | None,
) -> ModelInfo | None:
    """The catalog's facts for the model a profile named, or None.

    Three tiers, first match wins. The exact full id; then the id under any
    vendor — the query's provider prefix (``id.split("/")[0]``) is traded for
    the full id's vendor segment, so ``llama-3`` and ``groq/llama-3`` both
    find ``meta/llama-3``, the first full id in sort order when several do;
    then a normalized match folding case and the ``-`` ``.`` ``:`` ``_``
    separators (``llama3:8b`` ≡ ``llama-3-8b``). An id no tier reaches has no
    info: the cost stays NULL and the settings UI asks.

    The profile's two tunables override the catalog's; prices and
    capabilities are the catalog's or nobody's.
    """
    entries = load_catalog()
    by_bare, by_folded = _indexes(entries)
    found = (
        entries.get(model_id)
        or by_bare.get(_bare(model_id))
        or by_folded.get(_fold(_bare(model_id)))
    )
    if found is None:
        return None
    if profile_context_window is not None:
        found = replace(found, context_window=profile_context_window)
    if profile_max_output_tokens is not None:
        found = replace(found, max_output_tokens=profile_max_output_tokens)
    return found


def compute_cost(
    info: ModelInfo | None,
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    base_url: str | None,
    kind: str | None = None,
) -> float | None:
    """What one call cost in USD, by the truth table (design D4).

    The fake kind reaches no vendor at all, so its calls are free whatever
    else is known — and whatever its free-text model spelled; a fake has no
    meaningful ``base_url`` for the locality tier to read. Next, a local
    ``base_url`` (host in :data:`app.kernel.vendor.LOCAL_HOSTS`) is free even
    on a model no tier reaches. No info, a missing price, or an unreported
    token count leaves the cost unknown: NULL, never 0. Otherwise both prices
    are summed per million tokens and rounded to six decimals.
    """
    if kind == "fake":
        return 0.0
    if base_url is not None and httpx.URL(base_url).host in LOCAL_HOSTS:
        return 0.0
    if info is None:
        return None
    if info.input_price_per_mtok is None or info.output_price_per_mtok is None:
        return None
    if input_tokens is None or output_tokens is None:
        return None
    return round(
        input_tokens / 1e6 * info.input_price_per_mtok
        + output_tokens / 1e6 * info.output_price_per_mtok,
        6,
    )


def _bare(model_id: str) -> str:
    """The id without its leading vendor segment: ``groq/llama-3`` → ``llama-3``."""
    return model_id.split("/", 1)[1] if "/" in model_id else model_id


def _indexes(
    entries: Mapping[str, ModelInfo],
) -> tuple[dict[str, ModelInfo], dict[str, ModelInfo]]:
    """The two fallback indexes for this mapping, built once per mapping.

    The sort runs here — once — and never again: each index keeps the first
    full id in sort order per bare and per folded model segment, which is
    exactly the deterministic winner the scanned tiers used to walk to.
    """
    cached = _index_cache.get(id(entries))
    if cached is not None:
        return cached[1], cached[2]
    by_bare: dict[str, ModelInfo] = {}
    by_folded: dict[str, ModelInfo] = {}
    for full_id in sorted(entries):  # the one sort, at index build time
        info = entries[full_id]
        bare = _bare(full_id)
        by_bare.setdefault(bare, info)
        by_folded.setdefault(_fold(bare), info)
    _index_cache[id(entries)] = (entries, by_bare, by_folded)
    return by_bare, by_folded


def _fold(model_id: str) -> str:
    """Case- and separator-insensitive form: ``Llama-3.1:8b`` → ``llama318b``."""
    return model_id.lower().translate(_SEPARATORS)
