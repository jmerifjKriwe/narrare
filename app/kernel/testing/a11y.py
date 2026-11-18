"""A mechanical accessibility floor under every E2E flow: axe-core, WCAG A/AA.

``assert_accessible`` is the one line a test adds after its own assertions. It
injects the axe build the web app's devDependencies install, runs it on the
live DOM and fails on any violation. It is deliberately unable to pass without
having checked anything: a missing axe file, a script that never executed and
an evaluate that returned no verdict are all failures — a check that cannot
fail protects nothing.
"""

from pathlib import Path
from typing import cast

import pytest
from playwright.sync_api import Error, Page

ROOT = Path(__file__).resolve().parents[3]
AXE_PATH = ROOT / "web" / "node_modules" / "axe-core" / "axe.min.js"

# The verdict is formatted in the browser so the Python side only ever sees one
# value: "" is the pass, any other string is the failure text, and anything
# that is not a string means axe never delivered a verdict at all.
#
# ``exemptSelector`` (null for the ordinary floor) names the ONE feature whose
# own ink is deliberately below the AA floor — a sanctioned owner decision, not
# a defect. Only color-contrast nodes whose element matches the selector are
# set aside; every other rule on those nodes, and every rule on every other
# node, still fails. The count of set-aside nodes rides back so the caller can
# prove the exemption was exercised: an exemption that matches nothing axe
# flagged is stale, and a check that cannot fail protects nothing.
_AXE_RUN = r"""
(exemptSelector) => {
  // The element's own markup, because the target alone does not always name
  // what axe measured: a class selector can land on a node the rule should not
  // have matched at all (#451's `.px-1.5`), and a bare tag names nothing. One
  // bounded line — a section's outerHTML is tens of kilobytes, and the failure
  // text has to stay readable in a terminal and pasted into an issue.
  const MARKUP_CHARS = 200;
  const run = window.axe.run(document.body, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
  });
  return run.then((report) => {
    let exemptFlagged = 0;
    const blocks = [];
    for (const violation of report.violations) {
      let nodes = violation.nodes;
      if (exemptSelector && violation.id === "color-contrast") {
        const kept = [];
        for (const node of nodes) {
          // axe reports the node's selector path, not the element itself, so
          // resolve it to test the exemption. A target that no longer resolves
          // is never exempted — the check fails open, not silent.
          const element = document.querySelector(node.target.join(" "));
          if (element && element.matches(exemptSelector)) {
            exemptFlagged += 1;
          } else {
            kept.push(node);
          }
        }
        nodes = kept;
        if (nodes.length === 0) continue;
      }
      const shown = nodes.slice(0, 5).map((node) => {
        const raw = typeof node.html === "string" ? node.html : "(no html)";
        const html = raw.replace(/\s+/g, " ").trim();
        const line = html.length > MARKUP_CHARS ? `${html.slice(0, MARKUP_CHARS)}…` : html;
        return `    ${node.target.join(" ")}: ${node.failureSummary}\n      html: ${line}`;
      });
      const dropped = nodes.length - shown.length;
      const more =
        dropped > 0 ? `\n    … ${dropped} more node${dropped === 1 ? "" : "s"}` : "";
      const impact = violation.impact ?? "unknown";
      const head = `[${impact}] ${violation.id}: ${violation.help} (${violation.helpUrl})`;
      blocks.push(`${head}\n${shown.join("\n")}${more}`);
    }
    return { verdict: blocks.join("\n\n"), exemptFlagged };
  });
}
"""


def assert_accessible(page: Page, *, contrast_exempt_selector: str | None = None) -> None:
    """Fail unless ``page`` passes every WCAG A/AA rule axe-core checks.

    ``contrast_exempt_selector`` narrows the floor for ONE sanctioned feature:
    color-contrast violations on nodes matching the selector are expected (the
    feature's own deliberately below-AA ink, an owner decision the caller names
    in a comment beside the call). The exemption is node-level and rule-level —
    it never mutes another rule, another node, or the page. It must also be
    exercised: if axe flags no matching node, the exemption is stale and the
    check fails, so a feature that stops being below-AA cannot hide behind a
    dead exclusion. With no selector the floor is the whole page, as before.
    """
    if not AXE_PATH.is_file():
        pytest.fail(f"axe-core is missing: expected {AXE_PATH} (run: pnpm --dir web install)")
    # add_script_tag resolves only after the script has evaluated, so window.axe
    # exists when it returns; a page that blocked it anyway fails below.
    page.add_script_tag(path=str(AXE_PATH))
    try:
        result: object = page.evaluate(_AXE_RUN, contrast_exempt_selector)
    except Error as error:
        pytest.fail(f"axe did not execute: {error}")
    if not isinstance(result, dict):
        pytest.fail(f"axe did not execute: page.evaluate returned {result!r}")
    report = cast("dict[str, object]", result)
    verdict = report.get("verdict")
    if not isinstance(verdict, str):
        pytest.fail(f"axe did not execute: verdict was {verdict!r}")
    if verdict:
        pytest.fail(f"axe found WCAG A/AA violations on {page.url}:\n{verdict}")
    if contrast_exempt_selector is not None and report.get("exemptFlagged") == 0:
        pytest.fail(
            f"the contrast exemption is stale on {page.url}: axe flagged no node matching "
            f"{contrast_exempt_selector!r} — the sanctioned below-AA ink is gone, so the "
            "exclusion must go with it"
        )
