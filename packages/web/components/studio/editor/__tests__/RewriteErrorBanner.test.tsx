/**
 * RewriteErrorBanner tests — the standalone rewrite error surface.
 *
 * Audit B01 regression: pre-stream failures (e.g. 422) reset the flow to
 * idle with no suggestion, so the modal's error UI never mounted and the
 * modal "closed silently". The banner renders the structured error whenever
 * it is set and no suggestion modal is showing.
 *
 * @module RewriteErrorBanner.test
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import { RewriteErrorBanner } from "../RewriteErrorBanner";

const t = Object.assign((key: string) => key, {
  // Mirror next-intl v4's translator surface (`t.has`, see
  // CostsBreakdownTables): known studio.aiActions.* keys resolve (to the
  // key itself, so assertions use key strings); unknown keys report
  // has=false so the banner's userMessage fallback engages.
  has: (key: string) =>
    key === "aiActions.errorDefault" || key === "aiActions.retry" || key === "aiActions.dismiss",
}) as never;

function makeError(overrides: Partial<AIErrorResponse> = {}): AIErrorResponse {
  return {
    kind: "http",
    status: 422,
    i18nKey: "aiActions.errorDefault",
    userMessage: "mapped message",
    retryable: false,
    cause: new Error("boom"),
    ...overrides,
  };
}

describe("RewriteErrorBanner", () => {
  it("renders the resolved error message with role=alert", () => {
    render(<RewriteErrorBanner error={makeError()} onRetry={vi.fn()} onDismiss={vi.fn()} t={t} />);
    const banner = screen.getByTestId("rewrite-error-banner");
    expect(banner).toHaveAttribute("role", "alert");
    expect(banner).toHaveTextContent("aiActions.errorDefault");
  });

  it("falls back to userMessage when the i18n key is unknown", () => {
    render(
      <RewriteErrorBanner
        error={makeError({ i18nKey: "no.such.key" })}
        onRetry={vi.fn()}
        onDismiss={vi.fn()}
        t={t}
      />,
    );
    expect(screen.getByTestId("rewrite-error-banner")).toHaveTextContent("mapped message");
  });

  it("shows retry only for retryable errors and wires dismiss", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    const onDismiss = vi.fn();

    const { rerender } = render(
      <RewriteErrorBanner
        error={makeError({ retryable: false })}
        onRetry={onRetry}
        onDismiss={onDismiss}
        t={t}
      />,
    );
    expect(screen.queryByText("aiActions.retry")).toBeNull();

    rerender(
      <RewriteErrorBanner
        error={makeError({ retryable: true })}
        onRetry={onRetry}
        onDismiss={onDismiss}
        t={t}
      />,
    );
    await user.click(screen.getByText("aiActions.retry"));
    expect(onRetry).toHaveBeenCalledOnce();

    await user.click(screen.getByText("aiActions.dismiss"));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
