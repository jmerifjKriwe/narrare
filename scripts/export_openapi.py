#!/usr/bin/env python3
"""Write the OpenAPI document the web app consumes.

Generated, never edited: `just generate` runs this after the API changes and
commits the result. Importing the app instead of starting a server keeps the
recipe free of ports and timing.
"""

import json
from pathlib import Path

from app.api.main import app

TARGET = Path("web/lib/api/openapi.json")

type JSONScalar = str | int | float | bool | None
type JSONValue = JSONScalar | list[JSONValue] | dict[str, JSONValue]


def canonical_numbers(document: JSONValue) -> JSONValue:
    """Numbers in their canonical text form: an integral float is an integer.

    JSON has one number type, so `20.0` and `20` are the same value and the
    schema means the same either way. The text still has to be stable: release-
    please rewrites this file through Go's `encoding/json` when it bumps the
    version, and Go prints `20.0` as `20`. `just check-generated` compares
    bytes, so the writer must print what release-please would — issue #636,
    where every release PR went red on the `Field(le=20)` / `Field(gt=0)`
    bounds pydantic emits as floats.
    """
    if isinstance(document, dict):
        return {key: canonical_numbers(value) for key, value in document.items()}
    if isinstance(document, list):
        return [canonical_numbers(item) for item in document]
    if isinstance(document, float) and document.is_integer():
        return int(document)
    return document


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    document = json.dumps(
        canonical_numbers(app.openapi()), indent=2, sort_keys=True, ensure_ascii=False
    )
    TARGET.write_text(f"{document}\n", encoding="utf-8")
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
