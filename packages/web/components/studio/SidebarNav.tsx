"use client";

import { BarChart3, FileText, Library, MessageCircle, Package, Settings } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { SidebarKBBadge } from "./SidebarKBBadge";

/**
 * SidebarNav — Primary navigation for a novel workspace.
 *
 * Owns the nav-item list, active-link detection, and the navigation landmark.
 * The nav landmark always renders (empty when no novel is selected); nav items
 * appear only once a novelId is known. Extracted from Sidebar.tsx (RULE-04).
 */

interface NavItem {
  href: Route;
  label: string;
  icon: typeof FileText;
  key: string;
}

interface SidebarNavProps {
  novelId: string | undefined;
  /** Called after a nav item is clicked (e.g. to close a drawer). */
  onNavigate?: () => void;
}

export function SidebarNav({ novelId, onNavigate }: SidebarNavProps) {
  const t = useTranslations("studio");
  const pathname = usePathname();

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

  return (
    <nav aria-label={t("sidebar.navigation")} className="p-3 border-b border-border space-y-0.5">
      {navItems.map((item) => {
        const active = isActiveNav(item.href);
        return (
          <Link
            key={item.key}
            href={item.href}
            className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-md transition-colors text-sm ${
              active ? "bg-primary text-primary-foreground shadow-sm" : "hover:bg-accent"
            }`}
            onClick={onNavigate}
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
  );
}
