/**
 * The release-notes dialog: the release body as rendered Markdown, on the
 * shell's modal discipline (`@shell/ui/modalKeys` — Tab wraps inside the
 * panel, Escape closes) and the shell's tokens.
 *
 * The body is remote text from the release source, so it is rendered by
 * `react-markdown` with no raw-HTML plugin: the default escaping is the
 * security boundary — a `<script>` in a release body stays text. The explicit
 * `components` map styles the headings, lists, links and code without a
 * typography plugin, so the shell keeps one design surface.
 *
 * Two answers beyond the close door: "Ignore this version" hands the version
 * to the caller (the banner posts the dismissal), and the release link opens
 * the source in a new tab. Focus lands on the close button and returns to the
 * opener on unmount.
 */
import { useEffect, useId, useRef, type RefObject } from "react";
import ReactMarkdown, { type Components } from "react-markdown";

import { useTranslation } from "../lib/i18n";
import type { UpdateRead } from "../lib/updates";
import { FOCUS } from "../ui/card";
import { Icon } from "../ui/icons";
import { useModalKeys } from "../ui/modalKeys";

/** The release body's components: the project's type scale on the shell's
 *  tokens, no typography plugin. A raw `<h1>` in a release body becomes the
 *  panel's second level — the dialog title is the only h1-role heading. */
const MARKDOWN: Components = {
  h1: ({ children }) => (
    <h2 className="mb-3 mt-5 text-title font-semibold text-foreground first:mt-0">{children}</h2>
  ),
  h2: ({ children }) => (
    <h3 className="mb-2 mt-5 text-emph font-semibold text-foreground first:mt-0">{children}</h3>
  ),
  h3: ({ children }) => (
    <h4 className="mb-2 mt-4 text-label font-semibold text-foreground first:mt-0">{children}</h4>
  ),
  p: ({ children }) => (
    <p className="mb-3 text-body leading-relaxed text-foreground last:mb-0">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="mb-3 list-disc space-y-1 pl-5 text-body text-foreground">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-3 list-decimal space-y-1 pl-5 text-body text-foreground">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={`text-primary underline underline-offset-2 hover:text-foreground ${FOCUS}`}
    >
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="rounded bg-surface-container-low px-1 py-0.5 font-mono text-meta text-foreground">
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="mb-3 overflow-x-auto rounded bg-surface-container-low p-3 font-mono text-meta text-foreground">
      {children}
    </pre>
  ),
};

export function ReleaseNotesDialog({
  update,
  onClose,
  onDismiss,
  returnFocusTo,
}: {
  update: UpdateRead;
  onClose: () => void;
  onDismiss: () => void;
  /** The banner's notes button; focus returns here on unmount. */
  returnFocusTo?: RefObject<HTMLElement | null>;
}) {
  const t = useTranslation();
  const headingId = useId();
  const panelRef = useRef<HTMLDivElement | null>(null);
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  useModalKeys(panelRef, onClose);

  useEffect(() => {
    opener.current =
      returnFocusTo?.current ??
      (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    closeRef.current?.focus();
    return () => {
      // A dismissed version unmounts the opener with the strip. Focus then
      // falls to the shell's one main landmark, never to <body>.
      const target = opener.current?.isConnected === true
        ? opener.current
        : document.getElementById("main");
      target?.focus();
    };
  }, [returnFocusTo]);

  const version = update.latest_version ?? update.current_version;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-scrim p-4 backdrop-blur-[1px]"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        data-testid="release-notes-dialog"
        className="flex max-h-[80vh] w-full max-w-xl flex-col rounded-lg border border-border bg-surface-container-lowest shadow-overlay"
      >
        <div className="flex items-start justify-between gap-4 border-b border-rule px-6 py-4">
          <h2 id={headingId} className="text-title font-semibold text-foreground">
            {t("shell.update.heading", { version })}
          </h2>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label={t("shell.update.close")}
            className={`shrink-0 rounded p-1 text-muted transition-colors hover:bg-surface-container-low hover:text-foreground ${FOCUS}`}
          >
            <Icon name="cross" />
          </button>
        </div>

        <div className="overflow-y-auto px-6 py-4">
          <ReactMarkdown components={MARKDOWN}>{update.release_notes ?? ""}</ReactMarkdown>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule px-6 py-4">
          {update.release_url !== null ? (
            <a
              href={update.release_url}
              target="_blank"
              rel="noreferrer"
              className={`inline-flex items-center gap-1.5 text-meta font-medium text-primary underline underline-offset-2 hover:text-foreground ${FOCUS}`}
            >
              {t("shell.update.openRelease")}
              <Icon name="openInNew" size={14} />
            </a>
          ) : (
            <span aria-hidden="true" />
          )}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onDismiss}
              className={`rounded border border-border px-3 py-1.5 text-meta font-medium text-muted transition-colors hover:bg-surface-container-low hover:text-foreground ${FOCUS}`}
            >
              {t("shell.update.ignore")}
            </button>
            <button
              type="button"
              onClick={onClose}
              className={`rounded bg-primary px-3 py-1.5 text-meta font-medium text-primary-foreground transition-colors hover:opacity-90 ${FOCUS}`}
            >
              {t("shell.update.close")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
