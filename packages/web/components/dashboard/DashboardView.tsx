"use client"

import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { novelsApi } from "@/lib/api/client"
import { Button } from "@/components/ui/Button"
import { formatRelativeTime } from "@/lib/utils"
import type { NovelSummary } from "@/types"

export function DashboardView() {
  const t = useTranslations("dashboard")
  const tCommon = useTranslations("common")
  const router = useRouter()
  const queryClient = useQueryClient()

  const { data: novels = [], isLoading } = useQuery({
    queryKey: ["novels"],
    queryFn: novelsApi.list,
  })

  const createNovel = useMutation({
    mutationFn: () =>
      novelsApi.create({ title: "Untitled Novel", language: "en" }),
    onSuccess: (novel) => {
      queryClient.invalidateQueries({ queryKey: ["novels"] })
      router.push(`/novel/${novel.id}/editor`)
    },
  })

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1 className="dashboard-title">{t("title")}</h1>
        <Button
          onClick={() => createNovel.mutate()}
          loading={createNovel.isPending}
        >
          + {t("newNovel")}
        </Button>
      </div>

      {isLoading ? (
        <div className="dashboard-loading" aria-live="polite">
          <span>{tCommon("loading")}</span>
        </div>
      ) : novels.length === 0 ? (
        <div className="dashboard-empty">
          <p className="dashboard-empty-text">{t("noNovels")}</p>
          <p className="dashboard-empty-hint">{t("noNovelsHint")}</p>
          <Button
            onClick={() => createNovel.mutate()}
            loading={createNovel.isPending}
            className="dashboard-empty-cta"
          >
            + {t("newNovel")}
          </Button>
        </div>
      ) : (
        <div className="novel-grid">
          {novels.map((novel) => (
            <NovelCard key={novel.id} novel={novel} />
          ))}
        </div>
      )}

      <style jsx>{`
        .dashboard {
          max-width: 900px;
          margin: 0 auto;
          padding: var(--space-8) var(--space-4);
        }
        .dashboard-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: var(--space-8);
        }
        .dashboard-title {
          font-size: 1.5rem;
          font-weight: 700;
          letter-spacing: -0.02em;
        }
        .dashboard-loading {
          text-align: center;
          padding: var(--space-16);
          color: var(--color-text-secondary);
        }
        .dashboard-empty {
          text-align: center;
          padding: var(--space-16) var(--space-4);
          border: 2px dashed var(--color-border);
          border-radius: var(--radius-xl);
        }
        .dashboard-empty-text {
          font-size: 1.125rem;
          font-weight: 500;
          color: var(--color-text-primary);
          margin-bottom: var(--space-2);
        }
        .dashboard-empty-hint {
          color: var(--color-text-secondary);
          margin-bottom: var(--space-6);
        }
        .novel-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: var(--space-4);
        }
      `}</style>
    </div>
  )
}

function NovelCard({ novel }: { novel: NovelSummary }) {
  const t = useTranslations("dashboard")
  const router = useRouter()

  return (
    <button
      className="novel-card"
      onClick={() => router.push(`/novel/${novel.id}/editor`)}
      aria-label={`Open ${novel.title}`}
    >
      <div className="novel-card-header">
        <h2 className="novel-card-title">{novel.title}</h2>
        {novel.is_demo && (
          <span className="novel-card-badge">{t("demo")}</span>
        )}
      </div>
      {novel.author && (
        <p className="novel-card-author">{novel.author}</p>
      )}
      {novel.genre && (
        <p className="novel-card-genre">{novel.genre}</p>
      )}
      <p className="novel-card-updated">
        {t("lastEdited", { time: formatRelativeTime(novel.updated_at, novel.language) })}
      </p>

      <style jsx>{`
        .novel-card {
          text-align: left;
          padding: var(--space-4) var(--space-6);
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-xl);
          cursor: pointer;
          transition: border-color 0.15s, box-shadow 0.15s;
          width: 100%;
        }
        .novel-card:hover {
          border-color: var(--color-accent-muted);
          box-shadow: var(--shadow-md);
        }
        .novel-card-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: var(--space-2);
          margin-bottom: var(--space-2);
        }
        .novel-card-title {
          font-size: 1.0625rem;
          font-weight: 600;
          line-height: 1.3;
        }
        .novel-card-badge {
          font-size: 0.6875rem;
          font-weight: 600;
          padding: 0.15rem 0.5rem;
          border-radius: var(--radius-full);
          background: var(--color-accent-light);
          color: var(--color-accent);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          flex-shrink: 0;
        }
        .novel-card-author {
          font-size: 0.875rem;
          color: var(--color-text-secondary);
        }
        .novel-card-genre {
          font-size: 0.8125rem;
          color: var(--color-text-tertiary);
          margin-top: var(--space-1);
        }
        .novel-card-updated {
          font-size: 0.8125rem;
          color: var(--color-text-tertiary);
          margin-top: var(--space-3);
        }
      `}</style>
    </button>
  )
}
