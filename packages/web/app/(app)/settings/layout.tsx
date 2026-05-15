"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

const SETTINGS_NAV = [
  { href: "/settings/ai-providers", labelKey: "aiProviders" },
  { href: "/settings/ai-model", labelKey: "aiModel" },
  { href: "/settings/ai-prompts", labelKey: "aiPrompts" },
  { href: "/settings/appearance", labelKey: "appearance" },
] as const;

export default function SettingsLayout({ children }: { readonly children: React.ReactNode }) {
  const pathname = usePathname();
  const t = useTranslations("settings-ai.layout");

  // Mock translation for appearance until i18n is updated
  const translateLabel = (key: string) => {
    if (key === "appearance") return "Appearance";
    return t(key as any);
  };

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <nav className="w-56 shrink-0 border-r border-border bg-card p-6">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">
          {t("title")}
        </h2>
        <ul className="flex flex-col gap-1">
          {SETTINGS_NAV.map((item) => {
            const isActive = pathname === item.href;
            return (
              <li key={item.href}>
                <Link
                  href={item.href as Parameters<typeof Link>[0]["href"]}
                  className={cn(
                    "block px-3 py-2 rounded-lg text-sm transition-colors",
                    isActive
                      ? "bg-primary text-primary-foreground font-medium shadow-sm"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  )}
                  aria-current={isActive ? "page" : undefined}
                >
                  {translateLabel(item.labelKey)}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Content */}
      <main className="flex-1 min-w-0 overflow-y-auto">
        <div className="max-w-[800px] mx-auto p-8">{children}</div>
      </main>
    </div>
  );
}
