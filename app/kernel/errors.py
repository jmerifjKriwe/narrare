"""Shared refusal shapes: the machine-readable detail the surfaces localize.

The wire's failures carry ``{"detail": {"code": …, "detail": …}}`` — a code
the UI names in its own words and a sentence for the log and the curious.
The kernel owns the shape; every router raises its own ``HTTPException`` with
it, so the kernel imports no web framework.
"""


def coded_detail(
    code: str,
    detail: str = "",
    *,
    row: int | None = None,
    field: str | None = None,
) -> dict[str, str | int]:
    """The refusal's detail: the code the surfaces localize, its sentence,
    and the optional structure the surface marks instead of printing —
    ``row`` for a relation line's index in the sent list, ``field`` for an
    entity field's name. Absent structure adds no key."""
    payload: dict[str, str | int] = {"code": code, "detail": detail}
    if row is not None:
        payload["row"] = row
    if field is not None:
        payload["field"] = field
    return payload
