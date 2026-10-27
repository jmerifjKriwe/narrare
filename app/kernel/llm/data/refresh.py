"""Refresh the vendored models.dev snapshot — the project's one models.dev call.

Run by hand, from the checkout:

    python -m app.kernel.llm.data.refresh

Fetches ``https://models.dev/api.json``, reduces every model to the fields
the catalog keeps, and writes ``models.json`` beside this file with today's
date in ``snapshot_date``. Standard library only — and nothing here runs at
runtime: committing the refreshed file is the point.
"""

from datetime import date
from json import dump, loads
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

API_URL = "https://models.dev/api.json"
SNAPSHOT = Path(__file__).with_name("models.json")


def fetch_api() -> dict[str, Any]:
    """The full models.dev api.json, as served."""
    # Named, or models.dev refuses the library default with a 403.
    request = Request(API_URL, headers={"User-Agent": "narrare-catalog-refresh"})
    # The audited URL is API_URL: a pinned https literal, not user input.
    with urlopen(request, timeout=60) as response:  # noqa: S310
        return loads(response.read())


def compact(api: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The api reduced to the catalog's compact schema, keyed by full id.

    Prices are USD per million tokens and stay absent when the source has
    none — an absent price is NULL, never 0. ``supports_vision`` reads the
    input modalities; the three capability flags fall back to false where
    models.dev leaves them unsaid.
    """
    models: dict[str, dict[str, Any]] = {}
    for vendor, provider in api.items():
        for model_id, model in provider.get("models", {}).items():
            cost: dict[str, Any] = model.get("cost") or {}
            limit: dict[str, Any] = model.get("limit") or {}
            modalities: dict[str, Any] = model.get("modalities") or {}
            models[f"{vendor}/{model_id}"] = {
                "context_window": limit.get("context"),
                "max_output_tokens": limit.get("output"),
                "input_price_per_mtok": cost.get("input"),
                "output_price_per_mtok": cost.get("output"),
                "supports_json_schema": bool(model.get("structured_output", False)),
                "supports_tools": bool(model.get("tool_call", False)),
                "supports_vision": "image" in modalities.get("input", []),
            }
    return models


def main() -> None:
    """Write the snapshot fetched now, dated today, sorted and indented."""
    snapshot = {
        "snapshot_date": date.today().isoformat(),
        "models": dict(sorted(compact(fetch_api()).items())),
    }
    with SNAPSHOT.open("w") as file:
        dump(snapshot, file, indent=2, sort_keys=True)
        file.write("\n")
    print(f"{SNAPSHOT}: {len(snapshot['models'])} models, snapshot {snapshot['snapshot_date']}")


if __name__ == "__main__":
    main()
