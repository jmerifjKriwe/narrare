"""The one version literal in the codebase, and the one release-please writes.

The python release strategy updates any file named ``version.py`` beneath the
package path, so this line is the release PR's write target beside
``pyproject.toml``. Everything else derives from it: the app hands it to FastAPI,
``just generate`` carries it into ``web/lib/api/openapi.json``, and the config's
``extra-files`` patch the two ``package.json`` files and the ``narrare`` line in
``uv.lock``. Nothing else carries a version literal, and the derived lines are
written by the same release, so no copy can drift from the release.
"""

__version__ = "0.2.0"
