"""The vendored models.dev snapshot and the one script that refreshes it.

``models.json`` is data, not code: the kernel reads it through
:mod:`app.kernel.llm.catalog` and never over the network. ``refresh.py`` is
run by hand from the checkout (``python -m app.kernel.llm.data.refresh``)
when a newer snapshot is wanted — the only place in the project that talks
to models.dev. ``LICENSE`` is models.dev's, and travels with the snapshot.
"""
