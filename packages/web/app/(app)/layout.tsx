"use client";

import { useQuery } from "@tanstack/react-query";
import { Settings } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import { authApi } from "@/lib/api/client";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const t = useTranslations("common");
  const router = useRouter();

  const {
    data: user,
    isError,
    isLoading,
  } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: authApi.me,
    retry: false,
  });

  // Redirect to login when the /auth/me call fails (401 / network error)
  useEffect(() => {
    if (isError) {
      router.push("/login");
    }
  }, [isError, router]);

  // Minimal loading state — wordmark only, no spinner
  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[var(--color-bg-primary)]">
        <div className="text-center">
          <span
            className="text-2xl font-bold text-[var(--color-text-tertiary)]/60"
            style={{ fontFamily: "var(--font-display)", letterSpacing: "0.08em" }}
          >
            Narrare
          </span>
        </div>
        <span className="sr-only">{t("loading")}</span>
      </div>
    );
  }

  const displayName = user?.display_name || user?.email;

  return (
    <div className="flex h-screen flex-col">
      <header className="h-14 shrink-0 flex items-center justify-between px-8 bg-[var(--color-surface)] border-b border-[var(--color-border)] relative">
        {/* Subtle gradient accent line at bottom of header */}
        <div
          className="absolute bottom-0 left-0 right-0 h-[1px]"
          style={{
            background:
              "linear-gradient(90deg, transparent, var(--color-accent-muted), transparent)",
          }}
        />

        <Link
          href="/dashboard"
          className="text-[1.375rem] font-bold text-[var(--color-text-primary)] no-underline hover:text-[var(--color-accent)] transition-colors duration-300"
          style={{ fontFamily: "var(--font-display)", letterSpacing: "0.04em" }}
        >
          Narrare
        </Link>

        <div className="flex items-center gap-3">
          <Link
            href="/settings/ai-providers"
            className="text-[var(--color-text-tertiary)] hover:text-[var(--color-accent)] transition-colors"
            aria-label={t("settings")}
            title={t("settings")}
          >
            <Settings size={18} />
          </Link>
          <span className="text-[0.8125rem] text-[var(--color-text-tertiary)]">{displayName}</span>
        </div>
      </header>
      <main className="flex-1 min-h-0 overflow-hidden">{children}</main>
    </div>
  );
}
