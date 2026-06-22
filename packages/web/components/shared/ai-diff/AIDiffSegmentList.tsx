"use client";

import { useTranslations } from "next-intl";
import type { AIDiffSegment } from "@/lib/ai-diff/contracts";

interface AIDiffSegmentListProps {
  readonly segments: readonly AIDiffSegment[];
}

/**
 * Renders diff segments accessibly (CR-AUFG-07-18 AC #6):
 * - additions -> semantic `<ins>` + green tint + visible `+` marker + sr-only label
 * - removals  -> semantic `<del>` + red tint + strikethrough + visible `−` marker + sr-only label
 * - unchanged -> plain `<span>`
 *
 * Change type is conveyed by element semantics, a visible text marker, AND
 * color — never by color alone. The `sr-only` span gives screen readers an
 * explicit, translatable label (aria-label is not supported on `<ins>`/`<del>`
 * per biome useAriaPropsSupportedByRole, so an in-element visually-hidden
 * label is the accessible alternative).
 */
export function AIDiffSegmentList({ segments }: AIDiffSegmentListProps) {
  const t = useTranslations("studio");
  return (
    <>
      {segments.map((seg, i) => {
        // Stable, unique key: kind + index guarantees no collision even when
        // consecutive segments share identical text.
        const key = `${seg.kind}-${i}`;
        if (seg.kind === "added") {
          return (
            <ins
              key={key}
              className="rounded-sm bg-green-200/60 px-0.5 no-underline dark:bg-green-900/40"
            >
              <span aria-hidden="true" className="mr-0.5 font-mono">
                +
              </span>
              <span className="sr-only">{t("aiDiff.added")}: </span>
              {seg.text}
            </ins>
          );
        }
        if (seg.kind === "removed") {
          return (
            <del
              key={key}
              className="line-through rounded-sm bg-red-200/60 px-0.5 dark:bg-red-900/40"
            >
              <span aria-hidden="true" className="mr-0.5 font-mono">
                −
              </span>
              <span className="sr-only">{t("aiDiff.removed")}: </span>
              {seg.text}
            </del>
          );
        }
        return <span key={key}>{seg.text}</span>;
      })}
    </>
  );
}
