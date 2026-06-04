"use client";

import Image from "next/image";
import { useTranslations } from "next-intl";

/**
 * DashboardHeader — Top header bar for the dashboard view.
 *
 * Shows app logo, name, user avatar, display name, and logout button.
 * Extracted from DashboardView.tsx (RULE-04).
 */

interface UserData {
  display_name?: string;
  email: string;
}

interface DashboardHeaderProps {
  user: UserData;
  onLogout: () => void;
}

export function DashboardHeader({ user, onLogout }: DashboardHeaderProps) {
  const t = useTranslations("studio");
  const userInitial = (user.display_name || user.email).charAt(0).toUpperCase();
  const displayName = user.display_name || user.email;

  return (
    <header className="h-16 bg-card border-b border-border px-8 flex items-center justify-between flex-shrink-0">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-md bg-primary flex items-center justify-center overflow-hidden">
          <Image src="/logo.png" alt="Narrare" width={24} height={24} className="rounded" />
        </div>
        <span className="text-lg font-medium">{t("sidebar.appName")}</span>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3 pl-4 border-l border-border">
          <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
            <span className="text-sm font-medium text-primary-foreground">{userInitial}</span>
          </div>
          <span className="text-sm text-foreground hidden sm:block">{displayName}</span>
          <button
            type="button"
            onClick={onLogout}
            className="p-2 hover:bg-accent rounded-md transition-colors"
            aria-label={t("sidebar.logout")}
          >
            <span className="text-sm text-muted-foreground hover:text-foreground">
              {t("sidebar.logout")}
            </span>
          </button>
        </div>
      </div>
    </header>
  );
}
