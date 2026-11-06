"""The stack owns the E2E cache flag; a caller's extras cannot turn it off.

``run_stack(env=...)`` exists so a capability can point a provider at a
test-owned stand-in. The cache flag is not such a boundary: with it off, the
sweep's repeated hard navigations revalidate the whole dev graph again and
Chromium loses module bodies (#634, PR #642's review). It is written after the
extras for that reason.
"""

from app.kernel.testing import stack


def test_a_callers_env_cannot_turn_off_the_cache_flag() -> None:
    environment = stack._environment(  # pyright: ignore[reportPrivateUsage]  what the stack builds
        "narrare_v2_test", {"NARRE_E2E_NO_HTTP_CACHE": "0"}
    )
    assert environment["NARRE_E2E_NO_HTTP_CACHE"] == "1"
