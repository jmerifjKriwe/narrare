"""The browser's own language is fixed, so the machine's is not part of the result.

Every E2E asserts catalog text literally — "Titel", "Anlegen", "Wissen". The app
follows the browser when nobody has chosen a language, so an unpinned context
would let the locale of whoever runs the suite decide whether it passes. de-DE
is the language those assertions are written in.
"""

import pytest


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, object]) -> dict[str, object]:
    return {**browser_context_args, "locale": "de-DE"}
