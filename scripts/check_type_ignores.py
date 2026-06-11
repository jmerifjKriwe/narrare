#!/usr/bin/env python3
"""CLI entry point — delegates to check_type_ignores package."""

import importlib.util
import os
import sys


def _main() -> int:
    """Load the ``check_type_ignores`` package and run its CLI.

    Uses ``importlib`` to bypass the naming collision between this wrapper
    script (``scripts/check_type_ignores.py``) and the adjacent package
    directory (``scripts/check_type_ignores/``).
    """
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    pkg_dir = os.path.join(scripts_dir, "check_type_ignores")
    pkg_init = os.path.join(pkg_dir, "__init__.py")

    spec = importlib.util.spec_from_file_location(
        "check_type_ignores",
        pkg_init,
        submodule_search_locations=[pkg_dir],
    )
    if spec is None or spec.loader is None:
        msg = f"Could not load package spec from {pkg_init}"
        raise ImportError(msg)
    pkg = importlib.util.module_from_spec(spec)
    sys.modules["check_type_ignores"] = pkg
    spec.loader.exec_module(pkg)

    from check_type_ignores.main import main  # type: ignore[attr-defined]

    return main()


if __name__ == "__main__":
    sys.exit(_main())
