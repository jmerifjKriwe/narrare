"""The vendored models.dev catalog: one fact sheet per model id.

``data/models.json`` is a snapshot of ``https://models.dev/api.json`` reduced
to the fields this kernel needs, dated in ``snapshot_date`` and refreshed by
hand (:mod:`app.kernel.llm.data.refresh`) — nothing here touches the network
at runtime. Lookup tolerates how a profile spells a model, and the cost truth
table (design D4) turns what the catalog knows into what a call cost.
"""

from dataclasses import dataclass, replace
from json import loads
from pathlib import Path

import httpx

from app.kernel.vendor import LOCAL_HOSTS

SNAPSHOT = Path(__file__).parent / "data" / "models.json"

# The separators one vendor or another spells a model id with; the normalized
# tier folds them away (with case) so spelling cannot hide a known model.
_SEPARATORS = str.maketrans("", "", "-.:_")


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


def load_catalog() -> dict[str, ModelInfo]:
    """Every vendored model, keyed by its full ``vendor/model`` id."""
    payload = loads(SNAPSHOT.read_text())
    return {model_id: ModelInfo(**entry) for model_id, entry in payload["models"].items()}


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
    found = (
        entries.get(model_id)
        or _under_any_vendor(model_id, entries)
        or _normalized(model_id, entries)
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
) -> float | None:
    """What one call cost in USD, by the truth table (design D4).

    A local ``base_url`` (host in :data:`app.kernel.vendor.LOCAL_HOSTS`) is
    free whatever else is known — even an unknown model on this machine. No
    info, a missing price, or an unreported token count leaves the cost
    unknown: NULL, never 0. Otherwise both prices are summed per million
    tokens and rounded to six decimals.
    """
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


def _under_any_vendor(model_id: str, entries: dict[str, ModelInfo]) -> ModelInfo | None:
    """The first full id in sort order whose model segment is the query's own."""
    bare = _bare(model_id)
    for full_id in sorted(entries):
        if _bare(full_id) == bare:
            return entries[full_id]
    return None


def _normalized(model_id: str, entries: dict[str, ModelInfo]) -> ModelInfo | None:
    """The first full id in sort order whose model segment folds to the query's."""
    folded = _fold(_bare(model_id))
    for full_id in sorted(entries):
        if _fold(_bare(full_id)) == folded:
            return entries[full_id]
    return None


def _fold(model_id: str) -> str:
    """Case- and separator-insensitive form: ``Llama-3.1:8b`` → ``llama318b``."""
    return model_id.lower().translate(_SEPARATORS)
