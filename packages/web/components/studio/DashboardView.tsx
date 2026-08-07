"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useRef, useState } from "react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { authApi, novelsApi } from "@/lib/api/client";
import { novelsKeys } from "@/lib/hooks/novelsKeys";
import { useCreateSeries, useSeriesList } from "@/lib/hooks/useSeries";
import { useAuthStore } from "@/lib/stores/authStore";
import { DashboardHeader } from "./DashboardHeader";
import { DashboardLibrary } from "./DashboardLibrary";
import { DemoProjectCards } from "./DemoProjectCards";
import { NewSeriesDialog } from "./NewSeriesDialog";

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
    queryKey: novelsKeys.all,
    queryFn: novelsApi.list,
  });

  const deleteMutation = useMutation({
    mutationFn: novelsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: novelsKeys.all });
    },
  });

  // Series (Spec 1, Slice 4, Task 4.5) — rendered alongside standalone novels
  // in the mixed DashboardLibrary grid.
  const { data: series = [], isLoading: seriesLoading } = useSeriesList();
  const createSeriesMutation = useCreateSeries();
  const [newSeriesOpen, setNewSeriesOpen] = useState(false);

  function handleNewNovel() {
    router.push("/wizard");
  }

  function handleNewSeries() {
    setNewSeriesOpen(true);
  }

  function handleCreateSeries(title: string) {
    createSeriesMutation.mutate({ title }, { onSuccess: () => setNewSeriesOpen(false) });
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

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header bar */}
      <DashboardHeader user={user} onLogout={logout} />

      {/* Content area */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-6xl mx-auto">
          <div className="mb-8">
            <h1 className="text-2xl font-medium mb-2">{t("dashboard.title")}</h1>
            <p className="text-muted-foreground">{t("dashboard.subtitle")}</p>
          </div>

          <DashboardLibrary
            series={series}
            novels={novels}
            isLoading={novelsLoading || seriesLoading}
            onOpenSeries={(seriesId) => router.push(`/series/${seriesId}`)}
            onNewSeries={handleNewSeries}
            onDeleteNovel={handleDeleteNovel}
            onEditNovel={(novelId) => router.push(`/novel/${novelId}/settings`)}
            onNewNovel={handleNewNovel}
            isDeleting={deleteMutation.isPending}
            formatDate={formatDate}
          />

          {/* Demo projects section */}
          <div className="mt-12">
            <DemoProjectCards />
          </div>
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

      {/* New series dialog (Spec 1 — basic create flow) */}
      <NewSeriesDialog
        open={newSeriesOpen}
        onOpenChange={setNewSeriesOpen}
        onCreate={handleCreateSeries}
        isCreating={createSeriesMutation.isPending}
        createError={createSeriesMutation.isError}
      />
    </div>
  );
}
