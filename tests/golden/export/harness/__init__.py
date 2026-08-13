"""Golden-Pages acceptance-test harness (IO-001 / ADR-081 Slice 7).

Promoted + hardened from the Slice-5/6 inline probes
(``tests/golden/export/test_*.py``) and the bake-off PyMuPDF probes. This
package owns the three committed artifacts that make the export pipeline a
fire&forget robustness gate:

- :mod:`corpus`  — the varied manuscript-fixture registry + manuscript/options
  builders (renders every fixture via the REAL ``TypstPdfRenderer.render()``).
- :mod:`probes`  — the PyMuPDF probe library (8 probes, each an objective
  metric or invariant check).
- :mod:`baselines` — committed expected values + the ``--golden-update``
  regeneration path.
- :mod:`_pages` — the shared page-classification foundation (``PageClass`` +
  ``classify_pages`` + the ``group_lines`` / ``body_words`` geometry helpers)
  that six of the eight probes build on. Internal (extracted from ``probes``
  for RULE-04).

RULE-08 note: the golden test renders via ``TypstPdfRenderer.render()`` (the
production adapter), never a hand-rolled compile — that is what makes it an
acceptance test of the *whole* pipeline (pandoc HTML→Typst + wrapper assembly
+ typst compile). The harness itself spawns no typst/pandoc subprocess.
"""
