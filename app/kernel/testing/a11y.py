"""A mechanical accessibility floor under every E2E flow: axe-core, WCAG A/AA.

``assert_accessible`` is the one line a test adds after its own assertions. It
injects the axe build the web app's devDependencies install, runs it on the
live DOM and fails on any violation. It is deliberately unable to pass without
having checked anything: a missing axe file, a script that never executed and
an evaluate that returned no verdict are all failures — a check that cannot
fail protects nothing.
"""

from pathlib import Path

import pytest
from playwright.sync_api import Error, Page

ROOT = Path(__file__).resolve().parents[3]
AXE_PATH = ROOT / "web" / "node_modules" / "axe-core" / "axe.min.js"

# The verdict is formatted in the browser so the Python side only ever sees one
# value: "" is the pass, any other string is the failure text, and anything
# that is not a string means axe never delivered a verdict at all.
_AXE_RUN = r"""
() => {
  const run = window.axe.run(document.body, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
  });
  return run.then((report) => {
    const blocks = report.violations.map((violation) => {
      const nodes = violation.nodes
        .slice(0, 5)
        .map((node) => `    ${node.target.join(" ")}: ${node.failureSummary}`);
      const impact = violation.impact ?? "unknown";
      const head = `[${impact}] ${violation.id}: ${violation.help} (${violation.helpUrl})`;
      return `${head}\n${nodes.join("\n")}`;
    });
    return blocks.join("\n\n");
  });
}
"""


def assert_accessible(page: Page) -> None:
    """Fail unless ``page`` passes every WCAG A/AA rule axe-core checks."""
    if not AXE_PATH.is_file():
        pytest.fail(f"axe-core is missing: expected {AXE_PATH} (run: pnpm --dir web install)")
    # add_script_tag resolves only after the script has evaluated, so window.axe
    # exists when it returns; a page that blocked it anyway fails below.
    page.add_script_tag(path=str(AXE_PATH))
    try:
        verdict: object = page.evaluate(_AXE_RUN)
    except Error as error:
        pytest.fail(f"axe did not execute: {error}")
    if not isinstance(verdict, str):
        pytest.fail(f"axe did not execute: page.evaluate returned {verdict!r}")
    if verdict:
        pytest.fail(f"axe found WCAG A/AA violations on {page.url}:\n{verdict}")
