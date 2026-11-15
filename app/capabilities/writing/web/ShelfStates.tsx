/**
 * The shelf's loading and error states — the `shelf-states` draft's panels
 * 1 and 2, at the page's own geometry so nothing shifts when the answer
 * lands. The skeleton is the shell's quiet pulse on the soft token (the
 * draft's moving shimmer would need a keyframe the token surface does not
 * carry; the calm is the draft's own requirement). The error notice keeps
 * the draft's severity rule, cause/action block and retry — with the real
 * failure message, never the draft's invented gateway story, and a retry
 * that actually asks again. The „Offline-Cache öffnen" door is omitted:
 * no cache surface exists to open (a reason row, not a disabled fake).
 */

import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on the one control the error state offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** One quiet placeholder block — the soft token, the shell's pulse. */
function Bone({ className }: { className: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded bg-soft ${className}`} />;
}

export function ShelfLoading() {
  const t = useTranslation();
  return (
    <div role="status" className="space-y-8">
      {/* The metrics strip, values still outstanding. */}
      <div className="flex flex-wrap items-center gap-3">
        <Bone className="h-14 w-44 rounded-xl" />
        <Bone className="h-14 w-44 rounded-xl" />
        <Bone className="h-14 w-44 rounded-xl" />
      </div>
      {/* The hero skeleton — the cover's own footprint, no layout shift. */}
      <div className="rounded-xl border border-border bg-surface-container-low p-6 lg:p-8">
        <div className="flex flex-col items-center gap-8 md:flex-row">
          <Bone className="h-[264px] w-[192px] shrink-0 rounded-r-[5px]" />
          <div className="w-full flex-1 space-y-3">
            <Bone className="h-5 w-44" />
            <Bone className="h-8 w-3/4" />
            <Bone className="h-4 w-1/2" />
            <Bone className="h-1.5 w-full max-w-xl rounded-full" />
            <div className="flex gap-3 pt-2">
              <Bone className="h-10 w-52 rounded-lg" />
              <Bone className="h-10 w-32 rounded-lg" />
            </div>
          </div>
        </div>
      </div>
      {/* The grid skeleton — four cards, the draft's own rhythm. */}
      <div>
        <div className="mb-4 text-eyebrow uppercase text-muted">
          {t("writing.shelf.loading.library")}
        </div>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((at) => (
            <div key={at} className="rounded-xl border border-border bg-surface p-4">
              <Bone className="mx-auto h-[200px] w-[144px] rounded-r-[4px]" />
              <Bone className="mt-4 h-4 w-3/4" />
              <Bone className="mt-2 h-3 w-1/2" />
              <Bone className="mt-3 h-1 w-full rounded-full" />
            </div>
          ))}
        </div>
      </div>
      {/* The status foot — the draft's „Indizes laden…". */}
      <div className="flex items-center gap-2 text-meta text-muted">
        <span aria-hidden="true" className="h-2 w-2 animate-pulse rounded-full bg-outline-variant" />
        <span>{t("writing.shelf.loading")}</span>
      </div>
    </div>
  );
}

export function ShelfError({
  message,
  retrying,
  onRetry,
}: {
  message: string;
  retrying: boolean;
  onRetry: () => void;
}) {
  const t = useTranslation();
  return (
    <section
      role="alert"
      className="overflow-hidden rounded-xl border border-border bg-surface-container-low shadow-sm"
    >
      {/* The draft's 2px severity rule. */}
      <div aria-hidden="true" className="h-0.5 w-full bg-danger" />
      <div className="flex flex-col gap-4 p-6">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 shrink-0 text-danger">
            <Icon name="warning" size={24} />
          </span>
          <div>
            <h2 className={`${SERIF} text-title font-semibold leading-snug text-foreground`}>
              {t("writing.shelf.error.title")}
            </h2>
            {/* The real failure — the query's own message, status included. */}
            <p className="mt-0.5 font-mono text-meta text-danger">{message}</p>
          </div>
        </div>
        <div className="space-y-2 rounded-lg border border-border bg-surface-container-lowest/70 p-3 text-body leading-relaxed text-muted">
          <p>
            <strong className="font-semibold text-foreground">{t("writing.shelf.error.causeLabel")}</strong>{" "}
            {t("writing.shelf.error.cause")}
          </p>
          <p>
            <strong className="font-semibold text-foreground">{t("writing.shelf.error.actionLabel")}</strong>{" "}
            {t("writing.shelf.error.action")}
          </p>
        </div>
        <div className="flex items-center gap-3 pt-1">
          <button
            type="button"
            onClick={onRetry}
            disabled={retrying}
            className={`inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-surface-container-lowest px-3.5 py-2 text-label font-semibold text-foreground shadow-sm transition-all hover:border-primary active:scale-[0.98] ${FOCUS} ${retrying ? "cursor-not-allowed opacity-50" : ""}`}
          >
            <span className="text-primary">
              <Icon name="refresh" size={14} />
            </span>
            {retrying ? t("writing.shelf.error.retrying") : t("writing.shelf.error.retry")}
          </button>
        </div>
      </div>
    </section>
  );
}
