"use client";

import { AlertCircle } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

export default function EditorError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useTranslations("errors");
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 text-center">
      <div
        className="flex flex-col items-center gap-4 rounded-xl px-8 py-10"
        style={{ backgroundColor: "var(--color-error-light)" }}
      >
        <AlertCircle className="h-8 w-8" style={{ color: "var(--color-error)" }} />
        <h2 className="text-lg font-semibold" style={{ color: "var(--color-text-primary)" }}>
          {t("editor")}
        </h2>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => reset()}
            className="rounded-md px-4 py-2 text-sm font-medium transition-colors"
            style={{ backgroundColor: "var(--color-accent)", color: "#ffffff" }}
          >
            {t("retry")}
          </button>
          <Link
            href="/dashboard"
            className="rounded-md border px-4 py-2 text-sm font-medium transition-colors"
            style={{ borderColor: "var(--color-border)", color: "var(--color-text-secondary)" }}
          >
            {t("backToDashboard")}
          </Link>
        </div>
      </div>
    </div>
  );
}
