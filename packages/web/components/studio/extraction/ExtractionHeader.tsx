"use client";

/**
 * ExtractionHeader — Header bar for the ExtractionPanel modal.
 *
 * Extracted from ExtractionPanel for RULE-04 file size compliance.
 * Shows the panel title (loading or complete) and close button.
 */

import { Database, X } from "lucide-react";

interface ExtractionHeaderProps {
  readonly title: string;
  readonly closeLabel: string;
  readonly onClose: () => void;
}

export function ExtractionHeader({ title, closeLabel, onClose }: ExtractionHeaderProps) {
  return (
    <div className="flex items-center justify-between p-4 border-b border-border bg-card">
      <div className="flex items-center gap-2">
        <Database className="w-5 h-5 text-primary" />
        <h3 className="font-medium">{title}</h3>
      </div>
      <button
        type="button"
        onClick={onClose}
        className="p-1.5 rounded-md hover:bg-accent transition-colors"
        aria-label={closeLabel}
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
