"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Pencil, Plus, Trash2 } from "lucide-react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useRef, useState } from "react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { authApi, novelsApi } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/authStore";
import type { NovelSummary } from "@/types";

export function DashboardView() {
  const t = useTranslations("studio");
  const locale = useLocale();
  const router = useRouter();
  const logout = useAuthStore((s) => s.logout);
  const queryClient = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingTitle, setPendingTitle] = useState("");
  const pendingAction = useRef<(() => void) | null>(null);

  const {
    data: user,
    isError,
    isLoading: userLoading,
  } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: authApi.me,
    retry: false,
  });

  const { data: novels = [], isLoading: novelsLoading } = useQuery({
    queryKey: ["novels"],
    queryFn: novelsApi.list,
  });

  const deleteMutation = useMutation({
    mutationFn: novelsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["novels"] });
    },
  });

  function handleNewNovel() {
    router.push("/wizard");
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString(locale, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }

  function handleDeleteNovel(novelId: string, title: string) {
    pendingAction.current = () => deleteMutation.mutate(novelId);
    setPendingTitle(title);
    setConfirmOpen(true);
  }

  if (isError) {
    router.push("/login");
    return null;
  }

  if (userLoading || !user) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="w-12 h-12 rounded-md bg-primary flex items-center justify-center animate-pulse overflow-hidden">
          <Image
            src="/logo.png"
            alt="Narrare"
            width={32}
            height={32}
            className="rounded"
            priority
          />
        </div>
      </div>
    );
  }

  const userInitial = (user.display_name || user.email).charAt(0).toUpperCase();
  const displayName = user.display_name || user.email;

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header bar */}
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
              onClick={logout}
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

      {/* Content area */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-6xl mx-auto">
          <div className="mb-8">
            <h1 className="text-2xl font-medium mb-2">{t("dashboard.title")}</h1>
            <p className="text-muted-foreground">{t("dashboard.subtitle")}</p>
          </div>

          {/* Loading skeleton */}
          {novelsLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => (
                <div key={i} className="bg-card border border-border rounded-lg p-6 animate-pulse">
                  <div className="h-6 bg-muted rounded mb-2 w-3/4" />
                  <div className="h-4 bg-muted rounded mb-4 w-1/2" />
                  <div className="h-4 bg-muted rounded w-1/3" />
                </div>
              ))}
            </div>
          ) : novels.length === 0 ? (
            /* Empty state */
            <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
              <BookOpen className="w-16 h-16 mb-4 opacity-10" />
              <p className="text-lg mb-1">{t("dashboard.emptyTitle")}</p>
              <p className="text-sm">{t("dashboard.emptySubtitle")}</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {novels.map((novel: NovelSummary) => (
                <div
                  key={novel.id}
                  data-testid="novel-card"
                  className="group bg-card border border-border rounded-lg p-6 hover:shadow-md transition-shadow relative"
                >
                  {/* Edit button */}
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      router.push(`/novel/${novel.id}/settings`);
                    }}
                    className="absolute top-4 right-14 p-1.5 opacity-0 group-hover:opacity-100 hover:bg-accent rounded-md transition-opacity"
                    aria-label={t("dashboard.edit")}
                  >
                    <Pencil className="w-4 h-4 text-muted-foreground" />
                  </button>

                  {/* Delete button */}
                  <button
                    type="button"
                    data-testid="delete-novel-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteNovel(novel.id, novel.title);
                    }}
                    disabled={deleteMutation.isPending}
                    className="absolute top-4 right-4 p-1.5 opacity-0 group-hover:opacity-100 hover:bg-destructive/10 rounded-md transition-opacity"
                    aria-label={t("dashboard.delete")}
                  >
                    <Trash2 className="w-4 h-4 text-muted-foreground hover:text-destructive" />
                  </button>

                  {/* Card content — clickable */}
                  <a href={`/novel/${novel.id}`} className="block">
                    <h3 className="text-lg font-medium mb-1 pr-8">{novel.title}</h3>
                    <p className="text-sm text-muted-foreground mb-3">{novel.author}</p>

                    <div className="flex items-center gap-2 mb-4">
                      <span className="text-xs px-2 py-0.5 bg-muted rounded-md text-muted-foreground">
                        {novel.genre}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>
                        {t("dashboard.lastEdited")} {formatDate(novel.updated_at)}
                      </span>
                    </div>
                  </a>
                </div>
              ))}

              {/* New novel card */}
              <button
                type="button"
                data-testid="new-novel-btn"
                onClick={handleNewNovel}
                className="flex flex-col items-center justify-center bg-card border-2 border-dashed border-border rounded-lg p-6 hover:border-primary/50 hover:bg-accent transition-colors min-h-[180px]"
              >
                <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center mb-3">
                  <Plus className="w-5 h-5 text-muted-foreground" />
                </div>
                <span className="text-sm font-medium text-muted-foreground">
                  {t("dashboard.newNovel")}
                </span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Delete confirmation */}
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t("dashboard.delete")}
        description={t("dashboard.deleteConfirm", { title: pendingTitle })}
        confirmLabel={t("dashboard.delete")}
        variant="destructive"
        onConfirm={() => {
          pendingAction.current?.();
          pendingAction.current = null;
          setConfirmOpen(false);
        }}
      />
    </div>
  );
}
