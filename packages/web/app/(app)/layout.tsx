"use client";

import { useQuery } from "@tanstack/react-query";

import { BookOpen, Settings } from "lucide-react";
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

  // Minimal loading state
  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-center flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-primary flex items-center justify-center animate-pulse">
            <BookOpen className="w-6 h-6 text-primary-foreground" />
          </div>
          <span className="sr-only">{t("loading")}</span>
        </div>
      </div>
    );
  }

  const displayName = user?.display_name || user?.email;

  return (
    <div className="flex h-screen flex-col bg-background">
      <header className="h-16 shrink-0 flex items-center justify-between px-8 bg-card border-b border-border">
        <Link href="/dashboard" className="flex items-center gap-3 no-underline group">
          <div className="w-9 h-9 rounded-lg bg-primary flex items-center justify-center transition-transform group-hover:scale-105">
            <BookOpen className="w-5 h-5 text-primary-foreground" />
          </div>
          <div>
            <div
              className="text-[1.125rem] font-semibold text-foreground leading-none"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Narrare
            </div>
          </div>
        </Link>

        <div className="flex items-center gap-4">
          <Link
            href="/settings/ai-providers"
            className="flex items-center justify-center w-9 h-9 rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
            aria-label={t("settings")}
            title={t("settings")}
          >
            <Settings size={18} />
          </Link>
          <div className="flex items-center gap-2 pl-4 border-l border-border">
            <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center text-xs font-medium text-accent-foreground">
              {displayName?.charAt(0).toUpperCase()}
            </div>
            <span className="text-sm font-medium text-foreground">{displayName}</span>
          </div>
        </div>
      </header>
      <main className="flex-1 min-h-0 overflow-hidden">{children}</main>
    </div>
  );
}
