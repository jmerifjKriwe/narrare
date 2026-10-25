// @vitest-environment jsdom
/**
 * JobStatus's four visible states, rendered against the real catalog: a
 * queued row promises movement, a running row shows its progress, a failed
 * row names its error, and a done row reports the result count — the
 * count under the key the row's own job kind names, because a done row
 * wearing another kind's words would misreport the work. Each state is its
 * own assert-friendly attribute, because a status that never resolves — or
 * never says which of these it is — is the bug this component exists to
 * prevent.
 *
 * Expected strings come from the same t() the component renders with, so
 * the assertions pin the wiring (state → message), not one locale's words.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { Job } from "@shell/lib/api/client";
import { t } from "@shell/lib/i18n";

import { JobStatus } from "./JobStatus";

function job(overrides: Partial<Job>): Job {
  return {
    id: "6b1f2d3e-8c4a-4f2b-9d7e-1a2b3c4d5e6f",
    kind: "extract-entities",
    status: "queued",
    progress: null,
    error: null,
    result: null,
    ...overrides,
  };
}

/** The rendered element for a message, with its status attribute. */
function shown(message: string): HTMLElement {
  const element = screen.getByText(message);
  return element.closest("[data-job-status]") as HTMLElement;
}

afterEach(cleanup);

describe("JobStatus", () => {
  it("renders the queued row as promised movement", () => {
    render(<JobStatus job={job({})} />);
    expect(shown(t("jobs.queued")).getAttribute("data-job-status")).toBe("queued");
  });

  it("renders the running row with its progress", () => {
    render(<JobStatus job={job({ status: "running", progress: 40 })} />);
    const status = shown(t("jobs.runningProgress", { progress: 0.4 }));
    expect(status.getAttribute("data-job-status")).toBe("running");
    expect(status.textContent).toContain("40");
  });

  it("renders a running row without progress as plain movement", () => {
    // Progress is the handler's to report; NULL until it first does — the
    // panel must not wait for a number to say the work is going.
    render(<JobStatus job={job({ status: "running" })} />);
    expect(shown(t("jobs.running")).getAttribute("data-job-status")).toBe("running");
  });

  it("renders the failed row with its error text", () => {
    render(<JobStatus job={job({ status: "failed", error: "no handler for kind 'x'" })} />);
    const status = shown(t("jobs.failed", { error: "no handler for kind 'x'" }));
    expect(status.getAttribute("data-job-status")).toBe("failed");
    expect(status.textContent).toContain("no handler for kind 'x'");
  });

  it("renders the done row of an extraction with its suggestion count", () => {
    render(<JobStatus job={job({ status: "done", progress: 100, result: { suggestions: 3 } })} />);
    const status = shown(t("jobs.done.extract-entities", { count: 3 }));
    expect(status.getAttribute("data-job-status")).toBe("done");
    expect(status.textContent).toContain("3");
  });

  it("renders the done row of a consistency check with its finding count", () => {
    // The second job kind reads its own result key and its own done copy:
    // the check's findings, not the extraction's suggestions — a done row
    // must report the work the row's kind actually did.
    render(
      <JobStatus
        job={job({
          kind: "check-consistency",
          status: "done",
          progress: 100,
          result: { findings: 2 },
        })}
      />,
    );
    const status = shown(t("jobs.done.check-consistency", { count: 2 }));
    expect(status.getAttribute("data-job-status")).toBe("done");
    expect(status.textContent).toContain("2");
  });

  it("renders a done row of an unknown kind as the kind itself", () => {
    // A kind the map does not carry is contract drift: the row shows the
    // kind raw, never another kind's words — a zero count would invent a
    // result, and silence would read as work that never happened.
    render(
      <JobStatus
        job={job({
          kind: "translate-chapter",
          status: "done",
          progress: 100,
          result: { chapters: 7 },
        })}
      />,
    );
    const status = shown("translate-chapter");
    expect(status.getAttribute("data-job-status")).toBe("done");
  });
});
