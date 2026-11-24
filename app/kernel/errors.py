"""Shared refusal shapes: the machine-readable detail the surfaces localize.

The wire's failures carry ``{"detail": {"code": …, "detail": …}}`` — a code
the UI names in its own words and a sentence for the log and the curious.
The kernel owns the shape; every router raises its own ``HTTPException`` with
it, so the kernel imports no web framework.
"""


def coded_detail(code: str, detail: str = "") -> dict[str, str]:
    """The refusal's detail: the code the surfaces localize, and its sentence."""
    return {"code": code, "detail": detail}
