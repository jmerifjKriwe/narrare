"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Settings, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/Button";
import { novelsApi } from "@/lib/api/client";
import { formatRelativeTime } from "@/lib/utils";
import type { NovelSummary } from "@/types";

export function DashboardView() {
  const t = useTranslations("dashboard");
  const tCommon = useTranslations("common");

  const queryClient = useQueryClient();
  const router = useRouter();

  const { data: novels = [], isLoading } = useQuery({
    queryKey: ["novels"],
    queryFn: novelsApi.list,
  });

  const deleteNovel = useMutation({
    mutationFn: (novelId: string) => novelsApi.delete(novelId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["novels"] }),
  });

  const handleDelete = (novelId: string) => {
    if (!confirm(t("confirmDelete"))) return;
    deleteNovel.mutate(novelId);
  };

  return (
    <div className="h-full overflow-y-auto bg-gradient-to-b from-[var(--color-bg-primary)] to-[var(--color-bg-secondary)]">
      <div className="max-w-[1000px] mx-auto px-8 py-12">
        {/* Hero section — dramatic welcome */}
        <div className="mb-14 flex items-end justify-between animate-[narrare-fade-in_0.5s_ease-out]">
          <div>
            <h1 className="text-[2rem] font-bold leading-tight text-[var(--color-text-primary)] font-[family-name:var(--font-display)]">
              {t("title")}
            </h1>
            <div className="w-20 h-[2px] bg-[var(--color-accent)] mt-4 rounded-full" />
          </div>
          <Link
            href="/settings/ai-providers"
            className="text-sm text-[var(--color-text-tertiary)] hover:text-[var(--color-accent)] transition-colors flex items-center gap-1.5"
          >
            <Settings size={14} />
            {t("settings")}
          </Link>
        </div>

        {isLoading ? (
          <div className="text-center py-20 text-[var(--color-text-tertiary)]" aria-live="polite">
            <span>{tCommon("loading")}</span>
          </div>
        ) : novels.length === 0 ? (
          /* Empty state — atmospheric invitation */
          <div className="text-center py-24 px-8">
            <div className="text-3xl mb-6 text-[var(--color-accent-muted)]">✦</div>
            <p className="text-xl text-[var(--color-text-primary)] mb-3 leading-relaxed font-[family-name:var(--font-serif)] italic">
              {t("noNovelsQuote")}
            </p>
            <p className="text-[var(--color-text-tertiary)] mb-10 text-[0.9375rem]">
              {t("noNovelsHint")}
            </p>
            <Button onClick={() => router.push("/wizard")} size="lg">
              + {t("newNovel")}
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-6">
            {novels.map((novel) => (
              <NovelCard key={novel.id} novel={novel} onDelete={handleDelete} />
            ))}

            {/* New project card — inviting */}
            <button
              type="button"
              className="flex flex-col items-center justify-center p-8 rounded-2xl border-2 border-dashed border-[var(--color-border-strong)]/50 bg-transparent cursor-pointer text-[var(--color-text-tertiary)] hover:border-solid hover:border-[var(--color-accent-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-accent-light)]/50 transition-all duration-500 min-h-[220px] group"
              onClick={() => router.push("/wizard")}
              aria-label={t("newNovel")}
            >
              <div className="w-12 h-12 rounded-full border-2 border-current flex items-center justify-center mb-3 transition-transform duration-300 group-hover:scale-110">
                <span className="text-2xl font-[family-name:var(--font-display)]">+</span>
              </div>
              <span className="text-sm font-medium">{t("newNovel")}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function NovelCard({ novel, onDelete }: { novel: NovelSummary; onDelete: (id: string) => void }) {
  const t = useTranslations("dashboard");
  const router = useRouter();

  return (
    <>
      {/* biome-ignore lint/a11y/useSemanticElements: must use div, not button, to avoid nested <button> (HTML spec violation) */}
      <div
        role="button"
        tabIndex={0}
        className="group relative text-left rounded-2xl overflow-hidden cursor-pointer transition-all duration-300 ease-out w-full bg-gradient-to-b from-[var(--color-surface)] to-[var(--color-surface-raised)] border border-[var(--color-border)]/70 border-l-[3px] border-l-[var(--color-accent)] shadow-[var(--shadow-sm)] hover:shadow-[var(--shadow-lg)] hover:scale-[1.02]"
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = "var(--color-accent-muted)";
          e.currentTarget.style.borderLeftColor = "var(--color-accent)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = "";
          e.currentTarget.style.borderLeftColor = "var(--color-accent)";
        }}
        onClick={() => router.push(`/novel/${novel.id}/editor`)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            router.push(`/novel/${novel.id}/editor`);
          }
        }}
        aria-label={`Open ${novel.title}`}
      >
        {/* Delete button — appears on hover */}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onDelete(novel.id);
          }}
          className="absolute top-4 right-4 p-1.5 rounded-lg bg-[var(--color-surface)]/90
                   border border-[var(--color-border)]/50 text-[var(--color-text-tertiary)]
                   hover:text-[var(--color-error)] hover:border-[var(--color-error)]/30
                   opacity-0 group-hover:opacity-100 transition-all duration-200
                   cursor-pointer z-10"
          aria-label={t("deleteNovel")}
        >
          <Trash2 size={14} />
        </button>

        <div className="p-6">
          <div className="flex items-start justify-between gap-3 mb-3">
            <h2 className="text-[1.25rem] font-semibold leading-snug text-[var(--color-text-primary)] font-[family-name:var(--font-display)]">
              {novel.title}
            </h2>
            {novel.is_demo && (
              <span className="text-[0.625rem] font-bold py-1 px-2.5 rounded-md bg-[var(--color-accent-light)] text-[var(--color-accent)] uppercase tracking-[0.1em] shrink-0 border border-[var(--color-accent)]/15">
                {t("demo")}
              </span>
            )}
          </div>

          {novel.author && (
            <p className="text-[0.8125rem] text-[var(--color-text-secondary)] mb-1">
              {novel.author}
            </p>
          )}
          {novel.genre && (
            <p className="text-[0.75rem] text-[var(--color-text-tertiary)]">{novel.genre}</p>
          )}

          <div className="flex items-center gap-2 mt-5 pt-4 border-t border-[var(--color-border)]/60">
            <span className="text-[0.75rem] text-[var(--color-text-tertiary)] font-[family-name:var(--font-mono)]">
              {t("lastEdited", { time: formatRelativeTime(novel.updated_at, novel.language) })}
            </span>
          </div>
        </div>
      </div>
    </>
  );
}
