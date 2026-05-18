"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  BarChart3,
  FileText,
  Library,
  LogOut,
  Package,
  Plus,
  Settings,
} from "lucide-react";
import type { Route } from "next";
import Image from "next/image";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import { authApi, chaptersApi, volumesApi } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/authStore";
import { useEditorStore } from "@/lib/stores/editorStore";

interface NavItem {
  href: Route;
  label: string;
  icon: typeof FileText;
  key: string;
}

export function Sidebar() {
  const t = useTranslations("studio");
  const pathname = usePathname();
  const params = useParams();
  const logout = useAuthStore((s) => s.logout);
  const queryClient = useQueryClient();

  const novelId = params.id as string | undefined;
  const activeChapterId = useEditorStore((s) => s.activeChapterId);
  const setActiveChapterId = useEditorStore((s) => s.setActiveChapterId);
  const activeVolumeId = useEditorStore((s) => s.activeVolumeId);
  const setActiveVolumeId = useEditorStore((s) => s.setActiveVolumeId);

  const { data: user } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: authApi.me,
    // Deduplicated — already running in layout
  });

  // Fetch volumes for volume selector
  const { data: volumes = [] } = useQuery({
    queryKey: ["novels", novelId, "volumes"],
    queryFn: () => volumesApi.list(novelId!),
    enabled: !!novelId,
  });

  // Fetch chapters for current novel, optionally filtered by volume
  const { data: chapters = [] } = useQuery({
    queryKey: ["novels", novelId, "chapters", activeVolumeId],
    queryFn: () => chaptersApi.list(novelId!, activeVolumeId ?? undefined),
    enabled: !!novelId,
  });

  // Create chapter mutation
  const createChapterMutation = useMutation({
    mutationFn: () =>
      chaptersApi.create(novelId!, {
        title: t("sidebar.newChapterTitle"),
        ...(activeVolumeId ? { volume_id: activeVolumeId } : {}),
      }),
    onSuccess: (chapter) => {
      setActiveChapterId(chapter.id);
      queryClient.invalidateQueries({
        queryKey: ["novels", novelId!, "chapters"],
      });
    },
  });

  // Auto-select first chapter when chapters load and none is selected
  useEffect(() => {
    if (chapters.length > 0 && !activeChapterId) {
      setActiveChapterId(chapters[0].id);
    }
  }, [chapters, activeChapterId, setActiveChapterId]);

  const navItems: NavItem[] = novelId
    ? [
        {
          href: `/novel/${novelId}` as Route,
          label: t("sidebar.editor"),
          icon: FileText,
          key: "editor",
        },
        {
          href: `/novel/${novelId}/volumes` as Route,
          label: t("sidebar.volumes"),
          icon: Library,
          key: "volumes",
        },
        {
          href: `/novel/${novelId}/worldbuilding` as Route,
          label: t("sidebar.worldbuilding"),
          icon: Package,
          key: "worldbuilding",
        },
        {
          href: `/novel/${novelId}/analysis` as Route,
          label: t("sidebar.analysis"),
          icon: BarChart3,
          key: "analysis",
        },
        {
          href: `/novel/${novelId}/settings` as Route,
          label: t("sidebar.settings"),
          icon: Settings,
          key: "settings",
        },
      ]
    : [];

  function isActiveNav(href: Route): boolean {
    const hrefStr = String(href);
    if (
      hrefStr.startsWith("/novel/") &&
      !hrefStr.includes("/worldbuilding") &&
      !hrefStr.includes("/analysis") &&
      !hrefStr.includes("/volumes") &&
      !hrefStr.includes("/settings")
    ) {
      return pathname === hrefStr;
    }
    return pathname.startsWith(hrefStr);
  }

  const userInitial = user ? (user.display_name || user.email).charAt(0).toUpperCase() : "?";
  const displayName = user?.display_name || user?.email || "";

  return (
    <div className="w-72 bg-card border-r border-border flex flex-col h-full">
      {/* Logo area */}
      <div className="p-6 border-b border-border">
        <Link href="/" className="flex items-center gap-3 no-underline group">
          <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center transition-transform group-hover:scale-105 overflow-hidden">
            <Image
              src="/logo.png"
              alt="Narrare"
              width={32}
              height={32}
              className="rounded"
              priority
            />
          </div>
          <div>
            <h1 className="text-lg font-medium">{t("sidebar.appName")}</h1>
            <p className="text-xs text-muted-foreground">{t("sidebar.subtitle")}</p>
          </div>
        </Link>
      </div>

      {/* "All Novels" back link */}
      <div className="px-3 pt-3">
        <Link
          href="/"
          className="w-full flex items-center gap-2 px-4 py-2 rounded-md text-sm text-muted-foreground hover:bg-accent transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>{t("sidebar.allNovels")}</span>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="p-3 border-b border-border space-y-0.5">
        {navItems.map((item) => {
          const active = isActiveNav(item.href);
          return (
            <Link
              key={item.key}
              href={item.href}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-md transition-all text-sm ${
                active ? "bg-primary text-primary-foreground shadow-sm" : "hover:bg-accent"
              }`}
            >
              <item.icon className="w-4 h-4" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Chapter list — show for all novel routes */}
      {novelId && (
        <>
          {/* Volume selector — hidden when only default volume exists */}
          {volumes.length > 1 && (
            <div className="px-3 py-2 border-b border-border">
              <select
                value={activeVolumeId ?? ""}
                onChange={(e) => setActiveVolumeId(e.target.value || null)}
                className="w-full px-3 py-1.5 text-sm bg-card border border-border rounded-md"
                aria-label={t("volumes.title")}
              >
                <option value="">{t("volumes.allVolumes")}</option>
                {volumes.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.title}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="px-3 py-2 border-b border-border">
            <p className="text-xs text-muted-foreground px-4 py-1 uppercase">
              {t("sidebar.chapters")}
            </p>
          </div>
          <div className="flex-1 overflow-y-auto p-3">
            <div className="space-y-1">
              {chapters.map((chapter) => {
                const isActive = chapter.id === activeChapterId;
                return (
                  <button
                    type="button"
                    key={chapter.id}
                    onClick={() => setActiveChapterId(chapter.id)}
                    className={`w-full text-left px-4 py-3 rounded-md transition-all ${
                      isActive
                        ? "bg-card shadow-sm border border-border"
                        : "hover:bg-accent border border-transparent"
                    }`}
                  >
                    <div className="truncate text-sm">{chapter.title}</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {t("sidebar.words", { count: chapter.word_count })}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="p-4 border-t border-border">
            <button
              type="button"
              onClick={() => createChapterMutation.mutate()}
              disabled={createChapterMutation.isPending}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity shadow-sm disabled:opacity-50"
            >
              <Plus className="w-4 h-4" />
              <span className="text-sm">{t("sidebar.newChapter")}</span>
            </button>
          </div>
        </>
      )}

      {/* When no novel selected, fill remaining space */}
      {!novelId && <div className="flex-1" />}

      {/* User info + logout */}
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
            onClick={logout}
            className="p-2 hover:bg-accent rounded-md transition-colors flex-shrink-0"
            aria-label={t("sidebar.logout")}
          >
            <LogOut className="w-4 h-4 text-muted-foreground" />
          </button>
        </div>
      </div>
    </div>
  );
}
