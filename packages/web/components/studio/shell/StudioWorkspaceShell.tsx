"use client";

import { Menu } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Sidebar } from "@/components/studio/Sidebar";
import { FeatureTour } from "@/components/ui/feature-tour";
import { Toaster } from "@/components/ui/toaster";
import { FEATURE_TOUR_STEPS } from "@/lib/config/feature-tour-steps";

interface StudioWorkspaceShellProps {
  children: React.ReactNode;
}

export function StudioWorkspaceShell({ children }: StudioWorkspaceShellProps) {
  const t = useTranslations("studio");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!sidebarOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSidebarOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [sidebarOpen]);

  return (
    <div className="size-full flex bg-background">
      <div className="hidden lg:flex lg:shrink-0">
        <Sidebar variant="desktop" />
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center border-b border-border bg-card px-3 py-2 lg:hidden">
          <button
            type="button"
            aria-label={t("sidebar.openMenu")}
            onClick={() => setSidebarOpen(true)}
            className="rounded-md p-2 text-foreground hover:bg-accent focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <Menu className="h-5 w-5" />
          </button>
        </div>
        <main className="flex-1 min-h-0 min-w-0" aria-label={t("shell.workspaceMain")}>
          {children}
        </main>
      </div>
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 flex lg:hidden"
          role="dialog"
          aria-modal="true"
          aria-label={t("sidebar.navigation")}
        >
          <button
            type="button"
            aria-label={t("sidebar.closeMenu")}
            className="absolute inset-0 bg-background/70"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="relative z-10 h-full w-72 bg-card shadow-xl">
            <Sidebar variant="drawer" open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
          </div>
        </div>
      )}
      <Toaster />
      <FeatureTour steps={FEATURE_TOUR_STEPS} />
    </div>
  );
}
