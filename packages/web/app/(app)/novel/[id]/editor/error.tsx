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
      <div className="flex flex-col items-center gap-4 rounded-xl px-8 py-10 bg-destructive/10">
        <AlertCircle className="h-8 w-8 text-destructive" />
        <h2 className="text-lg font-semibold text-foreground">
          {t("editor")}
        </h2>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => reset()}
            className="rounded-md px-4 py-2 text-sm font-medium transition-colors bg-primary text-primary-foreground"
          >
            {t("retry")}
          </button>
          <Link
            href="/dashboard"
            className="rounded-md border border-border px-4 py-2 text-sm font-medium text-muted-foreground transition-colors"
          >
            {t("backToDashboard")}
          </Link>
        </div>
      </div>
    </div>
  );
}
