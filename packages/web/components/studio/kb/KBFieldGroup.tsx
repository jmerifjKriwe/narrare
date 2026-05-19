"use client";

/**
 * Accordion group component for KB field groups.
 *
 * Renders a collapsible section with:
 * - A header with icon (via lucide icon name), title, and rotating chevron
 * - Smooth animated expand/collapse using CSS grid-rows transition
 * - Content area with children
 */

import {
  BookOpen,
  ChevronDown,
  Eye,
  FileText,
  Heart,
  Info,
  Link2,
  MessageSquare,
  TrendingUp,
} from "lucide-react";
import { type ReactNode, useState } from "react";

/** Map known icon names to lucide components. */
const ICON_MAP: Record<string, typeof Info> = {
  Info,
  Eye,
  Heart,
  BookOpen,
  Link2,
  TrendingUp,
  MessageSquare,
  FileText,
};

interface KBFieldGroupProps {
  /** Lucide icon name (e.g., "Info", "Eye", "Heart"). */
  icon: string;
  /** Tailwind color class for the icon (e.g., "text-blue-500"). */
  iconColor: string;
  /** Localized group title. */
  title: string;
  /** Optional description / hint text. */
  description?: string;
  /** Whether the accordion is initially open. */
  defaultOpen?: boolean;
  /** Accordion content (field inputs). */
  children: ReactNode;
}

export function KBFieldGroup({
  icon,
  iconColor,
  title,
  description,
  defaultOpen = true,
  children,
}: KBFieldGroupProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const IconComponent = ICON_MAP[icon] ?? FileText;

  return (
    <div className="border border-border/60 rounded-lg bg-card shadow-sm overflow-hidden">
      {/* Header */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="w-full flex items-center gap-3 px-4 py-3.5
          bg-muted/30 hover:bg-muted/50 transition-colors duration-150
          text-left focus:outline-none focus:ring-2 focus:ring-inset focus:ring-primary/20"
        aria-expanded={isOpen}
      >
        <div className={`shrink-0 ${iconColor}`}>
          <IconComponent className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <span className="text-sm font-semibold text-foreground">{title}</span>
          {description && (
            <p className="text-xs text-muted-foreground/70 mt-0.5 truncate">{description}</p>
          )}
        </div>
        <ChevronDown
          className={`
            w-4 h-4 text-muted-foreground/50 shrink-0
            transition-transform duration-300 ease-in-out
            ${isOpen ? "rotate-180" : "rotate-0"}
          `}
        />
      </button>

      {/* Collapsible content */}
      <div
        className={`
          grid transition-[grid-template-rows] duration-300 ease-in-out
          ${isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}
        `}
      >
        <div className="overflow-hidden">
          <div className="px-4 pb-4 pt-2 space-y-3.5">{children}</div>
        </div>
      </div>
    </div>
  );
}
