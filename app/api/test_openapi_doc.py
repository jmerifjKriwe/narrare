"""The committed OpenAPI document is the contract the typed web client builds on.

`web/lib/api/openapi.json` feeds `openapi-typescript`, so a stale document means
a silently stale client. This test fails the moment the app and the committed
document disagree, which makes forgetting `just generate` a red suite instead
of a wrong UI.
"""

import json
from pathlib import Path

from app.api import main

DOC = Path(__file__).parents[2] / "web" / "lib" / "api" / "openapi.json"


def test_committed_openapi_document_matches_the_app() -> None:
    committed = json.loads(DOC.read_text(encoding="utf-8"))
    assert committed == main.app.openapi(), (
        "web/lib/api/openapi.json is stale: run `just generate` and commit the result"
    )
