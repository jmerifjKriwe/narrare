"use client"

import { useTranslations } from "next-intl"
import { useEditorStore } from "@/lib/stores/editorStore"
import { formatWordCount, estimateReadingTime } from "@/lib/utils"

export function StatusBar() {
  const t = useTranslations("editor")
  const { activeChapter, saveStatus } = useEditorStore()

  const wordCount = activeChapter?.word_count ?? 0
  const readingTime = estimateReadingTime(wordCount)

  const saveLabel = t(`saveStatus.${saveStatus}`)

  return (
    <div className="status-bar" role="status" aria-live="polite">
      <div className="status-left">
        {activeChapter && (
          <>
            <span className="status-words">
              {t("wordCount", { count: formatWordCount(wordCount) })}
            </span>
            <span className="status-separator">·</span>
            <span className="status-reading">
              {t("readingTime", { time: readingTime })}
            </span>
          </>
        )}
      </div>

      <div className="status-right">
        {saveLabel && (
          <span
            className={`status-save status-save--${saveStatus}`}
            aria-label={`Save status: ${saveStatus}`}
          >
            {saveStatus === "saving" && <span className="status-spinner" aria-hidden="true" />}
            {saveStatus === "error" && <span className="status-dot status-dot--error" aria-hidden="true" />}
            {saveStatus === "saved" && <span className="status-dot status-dot--success" aria-hidden="true" />}
            {saveLabel}
          </span>
        )}
      </div>

      <style jsx>{`
        .status-bar {
          height: 28px;
          border-top: 1px solid var(--color-border);
          background: var(--color-surface);
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 var(--space-4);
          flex-shrink: 0;
        }
        .status-left, .status-right {
          display: flex;
          align-items: center;
          gap: var(--space-2);
        }
        .status-words, .status-reading {
          font-size: 0.75rem;
          color: var(--color-text-tertiary);
        }
        .status-separator { color: var(--color-text-tertiary); font-size: 0.75rem; }
        .status-save {
          font-size: 0.75rem;
          display: flex;
          align-items: center;
          gap: var(--space-1);
        }
        .status-save--idle { color: transparent; }
        .status-save--saving { color: var(--color-text-secondary); }
        .status-save--saved { color: var(--color-success); }
        .status-save--error { color: var(--color-error); }
        .status-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
        }
        .status-dot--success { background: var(--color-success); }
        .status-dot--error { background: var(--color-error); }
        .status-spinner {
          width: 8px;
          height: 8px;
          border: 1.5px solid currentColor;
          border-top-color: transparent;
          border-radius: 50%;
          animation: spin 0.6s linear infinite;
          display: inline-block;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}
