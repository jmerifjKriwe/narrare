"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useRef, useState } from "react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { authApi, novelsApi } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/authStore";
import { DashboardHeader } from "./DashboardHeader";
import { NovelCardGrid } from "./NovelCardGrid";

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

          <NovelCardGrid
            novels={novels}
            isLoading={novelsLoading}
            onDelete={handleDeleteNovel}
            onEdit={(novelId) => router.push(`/novel/${novelId}/settings`)}
            onNew={handleNewNovel}
            isDeleting={deleteMutation.isPending}
            formatDate={formatDate}
          />
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
