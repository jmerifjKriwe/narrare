"""The update check: a newer release exists, and the user may read or ignore it.

Kernel machinery rather than a capability: the shell renders the notice and the
shell may not import a capability's code (design
``docs/superpowers/specs/2026-11-24-update-check-design.md``). The version
literal stays ``app.kernel.version.__version__``; nothing here repeats it.
"""
