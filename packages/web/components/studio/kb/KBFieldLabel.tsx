"use client";

/**
 * KBFieldLabel — field label with required indicator and inline help tooltip.
 *
 * Extracted from KBTypeField (RULE-04) so every field input shares one label
 * presentation: translated label text, a red asterisk for required fields, and
 * a small `?` (HelpCircle) icon that surfaces the field description as a native
 * browser tooltip via the wrapping span's `title` attribute.
 */

import { HelpCircle } from "lucide-react";
import type { ElementType } from "react";

interface KBFieldLabelProps {
  /** id of the associated input (makes the label clickable). Only used for `label`. */
  htmlFor?: string;
  /** Translated label text. */
  label: string;
  /** Whether the field is required (renders a red asterisk). */
  required?: boolean;
  /** Inline help text shown as a native tooltip on the `?` icon. */
  helpText?: string | null;
  /** Element type: "label" (default) or "span" (when no htmlFor applies). */
  as?: "label" | "span";
  /** Override the default label container classes (e.g. for inline layouts). */
  className?: string;
}

const DEFAULT_CLASS = "block text-xs font-medium text-muted-foreground mb-1.5";

export function KBFieldLabel({
  htmlFor,
  label,
  required = false,
  helpText = null,
  as = "label",
  className,
}: KBFieldLabelProps) {
  const Tag: ElementType = as;
  return (
    <Tag {...(as === "label" ? { htmlFor } : {})} className={className ?? DEFAULT_CLASS}>
      <span>{label}</span>
      {required && <span className="text-destructive ml-0.5">*</span>}
      {helpText && (
        <span
          title={helpText}
          className="inline-flex items-center ml-1 align-middle text-muted-foreground/40 hover:text-muted-foreground transition-colors"
        >
          <HelpCircle className="w-3.5 h-3.5" aria-label={helpText} role="img" />
        </span>
      )}
    </Tag>
  );
}
