"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/Button";
import { novelsApi } from "@/lib/api/client";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { NovelSummary } from "@/types";

export function DashboardView() {
  const t = useTranslations("dashboard");
  const tCommon = useTranslations("common");
  const router = useRouter();

  const { data: novels = [], isLoading } = useQuery({
    queryKey: ["novels"],
    queryFn: novelsApi.list,
  });

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-[900px] mx-auto p-8 px-4">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
          <Button onClick={() => router.push("/wizard")}>+ {t("newNovel")}</Button>
        </div>

        {isLoading ? (
          <div className="text-center p-16 text-[var(--color-text-secondary)]" aria-live="polite">
            <span>{tCommon("loading")}</span>
          </div>
        ) : novels.length === 0 ? (
          <div className="text-center p-16 px-4 border-2 border-dashed border-[var(--color-border)] rounded-[var(--radius-xl)]">
            <p className="text-lg font-medium text-[var(--color-text-primary)] mb-2">
              {t("noNovels")}
            </p>
            <p className="text-[var(--color-text-secondary)] mb-6">{t("noNovelsHint")}</p>
            <Button onClick={() => router.push("/wizard")}>+ {t("newNovel")}</Button>
          </div>
        ) : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
            {novels.map((novel) => (
              <NovelCard key={novel.id} novel={novel} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function NovelCard({ novel }: { novel: NovelSummary }) {
  const t = useTranslations("dashboard");
  const router = useRouter();

  return (
    <button
      type="button"
      className={cn(
        "text-left p-4 px-6 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-xl)]",
        "cursor-pointer transition-all duration-150 w-full",
        "hover:border-[var(--color-accent-muted)] hover:shadow-[var(--shadow-md)]",
      )}
      onClick={() => router.push(`/novel/${novel.id}/editor`)}
      aria-label={`Open ${novel.title}`}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <h2 className="text-[1.0625rem] font-semibold leading-tight">{novel.title}</h2>
        {novel.is_demo && (
          <span className="text-[0.6875rem] font-semibold py-0.5 px-2 rounded-full bg-[var(--color-accent-light)] text-[var(--color-accent)] uppercase tracking-wider shrink-0">
            {t("demo")}
          </span>
        )}
      </div>
      {novel.author && <p className="text-sm text-[var(--color-text-secondary)]">{novel.author}</p>}
      {novel.genre && (
        <p className="text-[0.8125rem] text-[var(--color-text-tertiary)] mt-1">{novel.genre}</p>
      )}
      <p className="text-[0.8125rem] text-[var(--color-text-tertiary)] mt-3">
        {t("lastEdited", { time: formatRelativeTime(novel.updated_at, novel.language) })}
      </p>
    </button>
  );
}
