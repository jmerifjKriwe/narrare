"use client";

import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef } from "react";
import { NameGenerator } from "./NameGenerator";

interface NameGeneratorModalProps {
  readonly novelId: string;
  readonly isOpen: boolean;
  readonly onClose: () => void;
}

export function NameGeneratorModal({ novelId, isOpen, onClose }: NameGeneratorModalProps) {
  const t = useTranslations("studio");
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  // Trap focus inside panel on open
  useEffect(() => {
    if (isOpen && panelRef.current) {
      panelRef.current.focus();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Side panel */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={t("generation.nameGenerator")}
        tabIndex={-1}
        className="relative ml-auto w-full max-w-md h-full bg-card border-l border-border shadow-2xl flex flex-col overflow-hidden animate-[narrare-slide-left_0.25s_ease-out]"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
          <span className="text-[0.875rem] font-semibold text-foreground">
            {t("generation.nameGenerator")}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors cursor-pointer"
            aria-label={t("generation.close")}
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          <NameGenerator novelId={novelId} />
        </div>
      </div>
    </div>
  );
}
