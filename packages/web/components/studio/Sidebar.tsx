"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Ruler, StickyNote, Zap } from "lucide-react";
import type { Route } from "next";
import Image from "next/image";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuickCapture } from "@/components/notes/QuickCaptureProvider";
import { IconButton } from "@/components/ui/icon-button";
import { authApi } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/authStore";
import { SidebarChapterList } from "./SidebarChapterList";
import { SidebarNav } from "./SidebarNav";
import { SidebarUserFooter } from "./SidebarUserFooter";

interface SidebarProps {
  variant?: "desktop" | "drawer";
  open?: boolean;
  onClose?: () => void;
}

export function Sidebar({ variant = "desktop", onClose }: SidebarProps) {
  const t = useTranslations("studio");
  const tNotes = useTranslations("notes");
  const params = useParams();
  const pathname = usePathname();
  const logout = useAuthStore((s) => s.logout);
  const quickCapture = useQuickCapture();

  const novelId = params.id as string | undefined;
  // The scratchpad entry sits outside SidebarNav's pathname matching, so it
  // owns its active state — mirroring SidebarNav's active visual language.
  const scratchpadActive = pathname === "/scratchpad";

  const { data: user } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: authApi.me,
    // Deduplicated — already running in layout
  });

  const handleNavigate = () => {
    if (variant === "drawer") onClose?.();
  };

  const containerClassName =
    variant === "drawer"
      ? "w-72 bg-card flex flex-col h-full"
      : "w-72 bg-card border-r border-border flex flex-col h-full";

  return (
    <div className={containerClassName}>
      {/* Logo area */}
      <div className="p-6 border-b border-border">
        <Link
          href="/"
          className="flex items-center gap-3 no-underline group"
          onClick={handleNavigate}
        >
          <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center transition-transform group-hover:scale-105 overflow-hidden">
            <Image
              src="/logo.png"
              alt="Narrare"
              width={32}
              height={32}
              className="rounded"
              priority
            />
          </div>
          <div>
            <h1 className="text-lg font-medium">{t("sidebar.appName")}</h1>
            <p className="text-xs text-muted-foreground">{t("sidebar.subtitle")}</p>
          </div>
        </Link>
      </div>

      {/* "All Novels" back link */}
      <div className="px-3 pt-3">
        <Link
          href="/"
          className="w-full flex items-center gap-2 px-4 py-2 rounded-md text-sm text-muted-foreground hover:bg-accent transition-colors"
          onClick={handleNavigate}
        >
          <ArrowLeft className="w-4 h-4" />
          <span>{t("sidebar.allNovels")}</span>
        </Link>
      </div>

      {/* Scratchpad — global, always available (NOTES-001) */}
      <div className="flex items-center gap-1 px-3 pt-1">
        <Link
          href="/scratchpad"
          data-testid="sidebar-scratchpad-link"
          aria-current={scratchpadActive ? "page" : undefined}
          className={`w-full flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-colors ${
            scratchpadActive
              ? "bg-primary text-primary-foreground shadow-sm"
              : "text-muted-foreground hover:bg-accent"
          }`}
          onClick={handleNavigate}
        >
          <StickyNote className="w-4 h-4" />
          <span>{tNotes("nav.label")}</span>
        </Link>
        <IconButton
          icon={Zap}
          label={tNotes("quickCapture.open")}
          // Follow-up b3: hover tooltip names the action AND its shortcut —
          // both keys already exist (quickCapture.open / shortcutHint), so
          // no new i18n keys are introduced.
          title={`${tNotes("quickCapture.open")} (${tNotes("quickCapture.shortcutHint")})`}
          data-testid="sidebar-quick-capture-button"
          onClick={() => quickCapture.open()}
        />
      </div>

      {/* Navigation */}
      <SidebarNav novelId={novelId} onNavigate={handleNavigate} />

      {/* Chapter list — show for all novel routes */}
      {novelId && <SidebarChapterList novelId={novelId} />}

      {/* When no novel selected, fill remaining space */}
      {!novelId && <div className="flex-1" />}

      {/* Dev Tools — only in development mode */}
      {process.env.NODE_ENV === "development" && (
        <div className="border-t border-border px-3 py-2">
          <p className="px-4 py-1 text-xs text-muted-foreground uppercase tracking-wider">
            {t("sidebar.devTools")}
          </p>
          <Link
            href={"/dev/design-tokens" as Route}
            className="w-full flex items-center gap-3 px-4 py-2 rounded-md text-sm hover:bg-accent transition-colors"
          >
            <Ruler className="w-4 h-4 text-muted-foreground" />
            <span>{t("sidebar.designTokens")}</span>
          </Link>
        </div>
      )}

      {/* User info + logout */}
      <SidebarUserFooter user={user} onLogout={logout} />
    </div>
  );
}
