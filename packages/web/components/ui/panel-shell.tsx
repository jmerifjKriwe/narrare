"use client";

import { type ReactNode, useRef } from "react";
import { usePanelFocus } from "@/lib/hooks/use-panel-focus";
import { cn } from "@/lib/utils";

interface PanelShellProps {
  /**
   * id of the heading that names this region; PanelShell renders that heading
   * and wires `aria-labelledby` to it so PanelHeader/PanelShell stay linked.
   */
  readonly titleId: string;
  /**
   * Accessible name for the panel, rendered as an sr-only heading whose id is
   * `titleId`. A resolved i18n string (RULE-16 — never hardcoded in callers).
   */
  readonly dialogLabel: string;
  readonly children: ReactNode;
  /** Side the panel attaches to. The dividing border is drawn on that side. */
  readonly side?: "right" | "left";
  /**
   * When false, renders nothing (and suspends focus management). Defaults to
   * true; most callers mount PanelShell conditionally instead.
   */
  readonly open?: boolean;
  /** Called when the user dismisses the panel with Escape. */
  readonly onClose: () => void;
  /** Optional `data-testid` for the shell element. */
  readonly testId?: string;
}

/**
 * Responsive shell for a single mounted element: a bottom-sheet at narrow
 * widths and a static sidebar at the `lg` breakpoint. Deliberately NOT a
 * dual desktop/mobile render — the adopter (EditorRightPanelSlot) hosts panels
 * that own streaming hooks (RULE-13), which must mount exactly once. Focus
 * move-in / Escape / focus-return are delegated to use-panel-focus.
 * Presentation only — does NOT own SSE/AI streaming (RULE-13).
 */
const SHELL_CLASSES =
  "fixed inset-x-0 bottom-0 z-30 flex max-h-[85vh] flex-col overflow-y-auto rounded-t-xl border border-border bg-card shadow-2xl lg:static lg:z-auto lg:flex lg:h-full lg:max-h-none lg:w-96 lg:shrink-0 lg:overflow-hidden lg:rounded-none lg:border-y-0 lg:shadow-none";

export function PanelShell({
  titleId,
  dialogLabel,
  children,
  side = "right",
  open = true,
  onClose,
  testId,
}: PanelShellProps) {
  const shellRef = useRef<HTMLElement | null>(null);
  usePanelFocus({ open, panelRef: shellRef, onClose });

  if (!open) return null;

  const desktopBorder = side === "left" ? "lg:border-l-0 lg:border-r" : "lg:border-r-0 lg:border-l";

  return (
    <section
      ref={shellRef}
      data-testid={testId}
      aria-labelledby={titleId}
      className={cn(SHELL_CLASSES, desktopBorder)}
    >
      <h2 id={titleId} className="sr-only">
        {dialogLabel}
      </h2>
      {children}
    </section>
  );
}
