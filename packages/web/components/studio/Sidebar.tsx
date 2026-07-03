"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  BarChart3,
  FileText,
  Library,
  MessageCircle,
  Package,
  Settings,
} from "lucide-react";
import type { Route } from "next";
import Image from "next/image";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { authApi } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/authStore";
import { SidebarChapterList } from "./SidebarChapterList";
import { SidebarKBBadge } from "./SidebarKBBadge";
import { SidebarUserFooter } from "./SidebarUserFooter";

interface NavItem {
  href: Route;
  label: string;
  icon: typeof FileText;
  key: string;
}

interface SidebarProps {
  variant?: "desktop" | "drawer";
  open?: boolean;
  onClose?: () => void;
}

export function Sidebar({ variant = "desktop", onClose }: SidebarProps) {
  const t = useTranslations("studio");
  const pathname = usePathname();
  const params = useParams();
  const logout = useAuthStore((s) => s.logout);

  const novelId = params.id as string | undefined;

  const { data: user } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: authApi.me,
    // Deduplicated — already running in layout
  });

  const navItems: NavItem[] = novelId
    ? [
        {
          href: `/novel/${novelId}` as Route,
          label: t("sidebar.editor"),
          icon: FileText,
          key: "editor",
        },
        {
          href: `/novel/${novelId}/volumes` as Route,
          label: t("sidebar.volumes"),
          icon: Library,
          key: "volumes",
        },
        {
          href: `/novel/${novelId}/worldbuilding` as Route,
          label: t("sidebar.worldbuilding"),
          icon: Package,
          key: "worldbuilding",
        },
        {
          href: `/novel/${novelId}/analysis` as Route,
          label: t("sidebar.analysis"),
          icon: BarChart3,
          key: "analysis",
        },
        {
          href: `/novel/${novelId}/chat` as Route,
          label: t("sidebar.chat"),
          icon: MessageCircle,
          key: "chat",
        },
        {
          href: `/novel/${novelId}/settings` as Route,
          label: t("sidebar.settings"),
          icon: Settings,
          key: "settings",
        },
      ]
    : [];

  function isActiveNav(href: Route): boolean {
    const hrefStr = String(href);
    if (
      hrefStr.startsWith("/novel/") &&
      !hrefStr.includes("/worldbuilding") &&
      !hrefStr.includes("/analysis") &&
      !hrefStr.includes("/chat") &&
      !hrefStr.includes("/volumes") &&
      !hrefStr.includes("/settings")
    ) {
      return pathname === hrefStr;
    }
    return pathname.startsWith(hrefStr);
  }

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

      {/* Navigation */}
      <nav aria-label={t("sidebar.navigation")} className="p-3 border-b border-border space-y-0.5">
        {navItems.map((item) => {
          const active = isActiveNav(item.href);
          return (
            <Link
              key={item.key}
              href={item.href}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-md transition-all text-sm ${
                active ? "bg-primary text-primary-foreground shadow-sm" : "hover:bg-accent"
              }`}
              onClick={handleNavigate}
            >
              <item.icon className="w-4 h-4" />
              <span className="flex-1">{item.label}</span>
              {item.key === "worldbuilding" && novelId && (
                <SidebarKBBadge novelId={novelId} active={active} />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Chapter list — show for all novel routes */}
      {novelId && <SidebarChapterList novelId={novelId} />}

      {/* When no novel selected, fill remaining space */}
      {!novelId && <div className="flex-1" />}

      {/* User info + logout */}
      <SidebarUserFooter user={user} onLogout={logout} />
    </div>
  );
}
