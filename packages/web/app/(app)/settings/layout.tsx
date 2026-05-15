"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

const SETTINGS_NAV = [
  { href: "/settings/ai-providers", labelKey: "aiProviders" },
  { href: "/settings/ai-model", labelKey: "aiModel" },
  { href: "/settings/ai-prompts", labelKey: "aiPrompts" },
] as const;

export default function SettingsLayout({ children }: { readonly children: React.ReactNode }) {
  const pathname = usePathname();
  const t = useTranslations("settings-ai.layout");

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <nav className="w-56 shrink-0 border-r border-[var(--color-border)] bg-[var(--color-surface)] p-6">
        <h2 className="text-[0.75rem] font-semibold uppercase tracking-[0.15em] text-[var(--color-text-tertiary)] mb-4">
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
                    "block px-3 py-2 rounded-lg text-[0.875rem] transition-colors",
                    isActive
                      ? "bg-[var(--color-accent-light)] text-[var(--color-accent)] font-medium"
                      : "text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-secondary)] hover:text-[var(--color-text-primary)]",
                  )}
                  aria-current={isActive ? "page" : undefined}
                >
                  {t(item.labelKey)}
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
