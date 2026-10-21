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


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    document = json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False)
    TARGET.write_text(f"{document}\n", encoding="utf-8")
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
