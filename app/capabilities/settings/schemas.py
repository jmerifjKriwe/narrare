"""The one setting: the language. ``None`` means "follow the browser"."""

from pydantic import BaseModel, field_validator

from app.generated.locales import LOCALES


class SettingsRead(BaseModel):
    locale: str | None


class SettingsUpdate(BaseModel):
    # Present and nullable, deliberately: ``{"locale": null}`` hands the choice
    # back to the browser, while ``{}`` is a client bug and must not mean the
    # same thing. A field with a default could not tell the two apart.
    locale: str | None

    @field_validator("locale")
    @classmethod
    def _carried_by_the_catalog(cls, value: str | None) -> str | None:
        # The catalog's filenames are the list of languages; a code outside it
        # would render an untranslated page and hide the mistake.
        if value is not None and value not in LOCALES:
            known = ", ".join(LOCALES)
            raise ValueError(f"unknown locale {value!r}; the catalog carries {known}")
        return value
