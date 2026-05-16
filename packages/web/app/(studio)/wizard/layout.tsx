"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpen } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import { authApi } from "@/lib/api/client";

/**
 * Wizard layout — auth-protected but WITHOUT the main sidebar.
 * Shows only a small logo header and centered content area.
 */
export default function WizardLayout({ children }: { children: React.ReactNode }) {
  const t = useTranslations("studio.sidebar");
  const router = useRouter();

  const { isError, isLoading } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: authApi.me,
    retry: false,
  });

  useEffect(() => {
    if (isError) {
      router.push("/login");
    }
  }, [isError, router]);

  if (isLoading || isError) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-center flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-md bg-primary flex items-center justify-center animate-pulse">
            <BookOpen className="w-6 h-6 text-primary-foreground" />
          </div>
          <span className="sr-only">{t("appName")}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Minimal top bar — logo only */}
      <header className="flex items-center px-6 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-md bg-primary flex items-center justify-center">
            <BookOpen className="w-4 h-4 text-primary-foreground" />
          </div>
          <span className="text-sm font-semibold">{t("appName")}</span>
        </div>
      </header>

      {/* Content fills the rest */}
      <main className="flex-1 flex items-start justify-center overflow-y-auto">{children}</main>
    </div>
  );
}
