"use client";

import { LogOut } from "lucide-react";
import { useTranslations } from "next-intl";

/**
 * SidebarUserFooter — User avatar, name, and logout button for the sidebar.
 *
 * Extracted from Sidebar.tsx (RULE-04).
 */

interface UserData {
  display_name?: string;
  email: string;
}

interface SidebarUserFooterProps {
  user: UserData | undefined;
  onLogout: () => void;
}

export function SidebarUserFooter({ user, onLogout }: SidebarUserFooterProps) {
  const t = useTranslations("studio");
  const userInitial = user ? (user.display_name || user.email).charAt(0).toUpperCase() : "?";
  const displayName = user?.display_name || user?.email || "";

  return (
    <div className="p-4 border-t border-border">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
          <span className="text-xs font-medium text-primary-foreground">{userInitial}</span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm truncate">{displayName}</p>
        </div>
        <button
          type="button"
          onClick={onLogout}
          className="p-2 hover:bg-accent rounded-md transition-colors flex-shrink-0"
          aria-label={t("sidebar.logout")}
        >
          <LogOut className="w-4 h-4 text-muted-foreground" />
        </button>
      </div>
    </div>
  );
}
