"use client";

/**
 * KBMoreFields — native progressive-disclosure wrapper for optional KB fields.
 *
 * Uses `<details>`/`<summary>` for consistency with the CR-AUFG-07-32 pattern
 * (AdvancedAiSettings). Collapsed by default so non-technical users see only the
 * required/basic fields first; optional fields are revealed on demand. The
 * summary label switches between "Show more fields" and "Show fewer fields".
 */

import { ChevronDown } from "lucide-react";
import { useTranslations } from "next-intl";
import { type ReactNode, useState } from "react";

interface KBMoreFieldsProps {
  /** Optional fields to reveal when expanded. */
  children: ReactNode;
}

export function KBMoreFields({ children }: KBMoreFieldsProps) {
  const t = useTranslations("studio");
  const [open, setOpen] = useState(false);

  return (
    <details className="group" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary
        className="cursor-pointer list-none [&::-webkit-details-marker]:hidden
          flex items-center gap-1.5 py-1 text-xs font-medium text-primary
          hover:text-primary/80 transition-colors"
      >
        <ChevronDown
          className="w-3.5 h-3.5 transition-transform duration-200 group-open:rotate-180"
          aria-hidden="true"
        />
        {open ? t("kb.fewerFields") : t("kb.moreFields")}
      </summary>

      <div className="space-y-3.5 pt-2">{children}</div>
    </details>
  );
}
