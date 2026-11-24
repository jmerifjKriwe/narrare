"""The update check's payloads: what the shell reads and what it dismisses."""

from datetime import datetime  # noqa: TC003  Pydantic resolves these at runtime

from pydantic import BaseModel, Field


class UpdateRead(BaseModel):
    """The answer the shell renders: the version, the last known release, and
    whether that release is still worth announcing.

    ``latest_version``, the notes and the link are the last known release, so
    an offline instance still shows what it heard before. ``update_available``
    is computed on the server — newer than the running version and not the
    dismissed one — and ``dismissed`` names the banner the reader asked to stop.
    """

    current_version: str
    latest_version: str | None
    update_available: bool
    release_notes: str | None
    release_url: str | None
    dismissed: bool
    checked_at: datetime | None


class UpdateDismiss(BaseModel):
    """The version the reader asked to ignore; a newer one announces again.

    Widths are the columns': the tag is at most 64 characters, so an over-long
    value is the gate's 422, never a Postgres error at the write.
    """

    version: str = Field(min_length=1, max_length=64)
