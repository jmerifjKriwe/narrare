// @vitest-environment jsdom
/**
 * The rail's drafted session card (screens/writing/workspace.html,
 * "Schreibsitzung heute"): the label and the §6.6 neutral where the words
 * today stand, with the goal bar and goal line out — the app tracks no
 * session, and a card that guessed one would print a number it does not
 * have (spec §6's interim rule).
 */
import { cleanup, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it } from "vitest";

import { t } from "@shell/lib/i18n";

import { SessionStats } from "./novel/SessionStats";

afterEach(cleanup);

describe("the drafted session card", () => {
  it("wears the drafted label with the neutral where the number stands", () => {
    const { container } = render(<SessionStats />);
    expect(screen.getByText(t("workspace.railSessionLabel"))).toBeTruthy();
    expect(screen.getByText(t("workspace.railSessionNone"))).toBeTruthy();
    // The neutral is the card's whole story: label and em dash, nothing else.
    expect(container.textContent).toBe(
      `${t("workspace.railSessionLabel")}${t("workspace.railSessionNone")}`,
    );
  });

  it("keeps the goal bar and the goal line out", () => {
    const { container } = render(<SessionStats />);
    expect(container.querySelector('[role="progressbar"]')).toBeNull();
    // No percent — the draft's "82% erreicht" needs a goal the app cannot hold.
    expect(container.textContent).not.toContain("%");
  });

  it("carries the interim comment with its follow-up anchor", () => {
    const source = readFileSync("../app/capabilities/writing/web/novel/SessionStats.tsx", "utf8");
    expect(source).toContain("// interim: no session tracking — #818");
  });
});
