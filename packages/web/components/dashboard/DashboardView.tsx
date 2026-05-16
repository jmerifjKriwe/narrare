"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Plus, Trash2 } from "lucide-react";
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
    <div className="h-full overflow-y-auto bg-background">
      <div className="max-w-[1000px] mx-auto px-8 py-12">
        {/* Hero section */}
        <div className="mb-14 flex items-end justify-between animate-[narrare-fade-in_0.5s_ease-out]">
          <div>
            <h1 className="text-4xl font-semibold leading-tight text-foreground">
              {t("title")}
            </h1>
            <div className="w-20 h-1 bg-primary mt-4 rounded-full opacity-80" />
          </div>
        </div>

        {isLoading ? (
          <div className="text-center py-20 text-muted-foreground" aria-live="polite">
            <span className="animate-pulse">{tCommon("loading")}...</span>
          </div>
        ) : novels.length === 0 ? (
          /* Empty state */
          <div className="text-center py-24 px-8 border border-border border-dashed rounded-lg bg-card">
            <div className="flex justify-center mb-6">
              <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
                <BookOpen className="w-6 h-6 text-muted-foreground/50" />
              </div>
            </div>
            <p className="text-xl text-foreground mb-3 leading-relaxed italic">
              {t("noNovelsQuote")}
            </p>
            <p className="text-muted-foreground mb-10 text-sm">{t("noNovelsHint")}</p>
            <Button onClick={() => router.push("/wizard")} size="lg">
              + {t("newNovel")}
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-6">
            {novels.map((novel) => (
              <NovelCard key={novel.id} novel={novel} onDelete={handleDelete} />
            ))}

            {/* New project card */}
            <button
              type="button"
              className="flex flex-col items-center justify-center p-8 rounded-xl border-2 border-dashed border-border bg-transparent cursor-pointer text-muted-foreground hover:border-primary/50 hover:text-primary hover:bg-accent/50 transition-all duration-300 min-h-[200px] group"
              onClick={() => router.push("/wizard")}
              aria-label={t("newNovel")}
            >
              <div className="w-12 h-12 rounded-full border border-current flex items-center justify-center mb-3 transition-transform duration-300 group-hover:scale-110">
                <span className="text-2xl">+</span>
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
        className="group relative text-left rounded-xl overflow-hidden cursor-pointer transition-all duration-300 ease-out w-full bg-card border border-border shadow-sm hover:shadow-md hover:border-primary/40 hover:-translate-y-1"
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
          className="absolute top-4 right-4 p-1.5 rounded-lg bg-background/90
                   border border-border/50 text-muted-foreground
                   hover:text-destructive hover:border-destructive/30 hover:bg-destructive/10
                   opacity-0 group-hover:opacity-100 transition-all duration-200
                   cursor-pointer z-10"
          aria-label={t("deleteNovel")}
        >
          <Trash2 size={14} />
        </button>

        <div className="p-6">
          <div className="flex items-start justify-between gap-3 mb-3">
            <h2 className="text-lg font-semibold leading-snug text-foreground line-clamp-2">
              {novel.title}
            </h2>
            {novel.is_demo && (
              <span className="text-[10px] font-semibold py-1 px-2 rounded-md bg-accent text-accent-foreground uppercase tracking-wider shrink-0 border border-border">
                {t("demo")}
              </span>
            )}
          </div>

          {novel.author && <p className="text-sm text-muted-foreground mb-1">{novel.author}</p>}
          {novel.genre && <p className="text-xs text-muted-foreground/80">{novel.genre}</p>}

          <div className="flex items-center gap-2 mt-5 pt-4 border-t border-border">
            <span className="text-xs text-muted-foreground/70 font-mono">
              {t("lastEdited", { time: formatRelativeTime(novel.updated_at, novel.language) })}
            </span>
          </div>
        </div>
      </div>
    </>
  );
}
