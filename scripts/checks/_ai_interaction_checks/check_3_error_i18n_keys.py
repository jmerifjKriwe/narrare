from __future__ import annotations

import re

from ._shared import I18N_DIR, display_path, is_excluded

REQUIRED_ERROR_KEYS = [
    "errorApiKey",
    "errorTextTooLong",
    "errorRateLimit",
    "errorTimeout",
    "errorConnection",
    "errorParse",
    "errorDefault",
]

REQUIRED_LOCALES = ["de", "en", "fr"]


def check_error_i18n_keys(excludes: set[str]) -> tuple[list[str], list[str]]:
    passes: list[str] = []
    violations: list[str] = []

    for locale in REQUIRED_LOCALES:
        studio_json = I18N_DIR / locale / "studio.json"
        if not studio_json.exists():
            violations.append(f"Missing locale file: {display_path(studio_json)}")
            continue

        try:
            content = studio_json.read_text(encoding="utf-8")
        except OSError as e:
            violations.append(f"Cannot read {display_path(studio_json)}: {e}")
            continue

        for key in REQUIRED_ERROR_KEYS:
            if re.search(rf'"{key}"\s*:', content):
                passes.append(f"{locale}/studio.json has aiActions.{key} +")
            else:
                exclude_key = f"{locale}/{key}"
                if is_excluded(exclude_key, excludes):
                    passes.append(f"[EXCLUDED] {exclude_key} -- excluded from Check 3")
                else:
                    violations.append(
                        f"{locale}/studio.json MISSING aiActions.{key}\n"
                        f'  -> Add: "{key}": "<translated message>" to aiActions block'
                    )

    return passes, violations
