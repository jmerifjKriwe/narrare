"""Renderer adapter skeletons for the export pipeline (RULE-08).

Each external binary (Typst, pandoc) is invoked inside exactly one module in
this package — enforced by the RULE-08 AST confinement checker
(``scripts/architecture/_checkers/export_binary_confinement.py``). Slice 0 ships
boundary skeletons only: each renderer declares ``format`` + ``is_available()``
and raises ``NotImplementedError`` from ``render()``. Real rendering lands in
Slices 3 (Markdown), 4 (EPUB), and 6 (PDF).
"""
