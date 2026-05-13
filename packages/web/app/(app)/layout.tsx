"use client";

import { useQuery } from "@tanstack/react-query";
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
      <div className="flex h-screen items-center justify-center">
        <span
          className="text-xl font-bold tracking-wide text-[var(--color-text-tertiary)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Narrare
        </span>
        <span className="sr-only">{t("loading")}</span>
      </div>
    );
  }

  const displayName = user?.display_name || user?.email;

  return (
    <div className="flex h-screen flex-col">
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-surface)] px-6">
        <Link
          href="/dashboard"
          className="text-xl font-bold tracking-wide text-[var(--color-text-primary)] no-underline transition-colors hover:text-[var(--color-accent)]"
          style={{ fontFamily: "var(--font-display)" }}
        >
          Narrare
        </Link>
        <span className="text-sm text-[var(--color-text-tertiary)]">{displayName}</span>
      </header>
      <main className="flex-1 min-h-0 overflow-hidden">{children}</main>
    </div>
  );
}
