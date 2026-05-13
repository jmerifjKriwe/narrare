"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/Button";
import { novelsApi } from "@/lib/api/client";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { NovelSummary } from "@/types";

export function DashboardView() {
  const t = useTranslations("dashboard");
  const tCommon = useTranslations("common");

  const queryClient = useQueryClient();

  const { data: novels = [], isLoading } = useQuery({
    queryKey: ["novels"],
    queryFn: novelsApi.list,
  });

  const createNovel = useMutation({
    mutationFn: () => novelsApi.create({}),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["novels"] }),
  });

  return (
    <div className="h-full overflow-y-auto bg-[var(--color-bg-primary)]">
      <div className="max-w-[960px] mx-auto p-8 px-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-10">
          <h1
            className="text-2xl font-bold tracking-tight"
            style={{ fontFamily: "var(--font-display)" }}
          >
            {t("title")}
          </h1>
          <Button onClick={() => createNovel.mutate()} loading={createNovel.isPending}>
            + {t("newNovel")}
          </Button>
        </div>

        {isLoading ? (
          <div className="text-center p-16 text-[var(--color-text-tertiary)]" aria-live="polite">
            <span>{tCommon("loading")}</span>
          </div>
        ) : novels.length === 0 ? (
          /* Empty state — literary invitation */
          <div className="text-center p-16 px-6 border border-[var(--color-border)] rounded-xl bg-[var(--color-surface)]">
            <p
              className="text-lg italic text-[var(--color-text-secondary)] mb-2"
              style={{ fontFamily: "var(--font-serif)" }}
            >
              {t("noNovelsQuote")}
            </p>
            <p className="text-[var(--color-text-tertiary)] mb-8 text-[0.9375rem]">
              {t("noNovelsHint")}
            </p>
            <Button onClick={() => createNovel.mutate()} loading={createNovel.isPending}>
              + {t("newNovel")}
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-5">
            {novels.map((novel) => (
              <NovelCard key={novel.id} novel={novel} />
            ))}

            {/* New project card */}
            <button
              type="button"
              className="flex flex-col items-center justify-center p-6 border border-dashed border-[var(--color-border)] rounded-xl bg-transparent cursor-pointer text-[var(--color-text-tertiary)] hover:border-[var(--color-accent-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-accent-light)] transition-all duration-300 min-h-[180px] group"
              onClick={() => createNovel.mutate()}
              aria-label={t("newNovel")}
            >
              <span className="text-2xl mb-2 opacity-40 group-hover:opacity-70 transition-opacity">
                +
              </span>
              <span className="text-sm font-medium">{t("newNovel")}</span>
            </button>
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
        "group relative text-left bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl overflow-hidden",
        "cursor-pointer transition-all duration-300 ease-out w-full",
        "hover:border-[var(--color-accent-muted)] hover:shadow-[var(--shadow-lg)] hover:-translate-y-0.5",
      )}
      onClick={() => router.push(`/novel/${novel.id}/editor`)}
      aria-label={`Open ${novel.title}`}
    >
      {/* Book spine accent */}
      <div className="absolute left-0 top-0 bottom-0 w-1 bg-[var(--color-accent)] opacity-50 group-hover:opacity-100 transition-opacity duration-300" />

      <div className="p-5 pl-6">
        <div className="flex items-start justify-between gap-2 mb-2">
          <h2
            className="text-[1.0625rem] font-semibold leading-tight text-[var(--color-text-primary)]"
            style={{ fontFamily: "var(--font-display)" }}
          >
            {novel.title}
          </h2>
          {novel.is_demo && (
            <span className="text-[0.625rem] font-semibold py-0.5 px-2 rounded-full bg-[var(--color-accent-light)] text-[var(--color-accent)] uppercase tracking-wider shrink-0">
              {t("demo")}
            </span>
          )}
        </div>
        {novel.author && (
          <p className="text-sm text-[var(--color-text-secondary)]">{novel.author}</p>
        )}
        {novel.genre && (
          <p className="text-[0.8125rem] text-[var(--color-text-tertiary)] mt-1">{novel.genre}</p>
        )}
        <div className="flex items-center gap-2 mt-4 pt-3 border-t border-[var(--color-border)]">
          <span className="text-[0.8125rem] text-[var(--color-text-tertiary)]">
            {t("lastEdited", { time: formatRelativeTime(novel.updated_at, novel.language) })}
          </span>
        </div>
      </div>
    </button>
  );
}
