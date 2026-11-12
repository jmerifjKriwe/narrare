import { useTranslation } from "@shell/lib/i18n";
import { Notice } from "@shell/ui/Notice";

/**
 * The shelf's wait (`screens/library/shelf-states.html`, panel 1): the
 * page's own shape painted in quiet placeholders — the metrics strip, the
 * hero with its cover, the toolbar and the grid — so the answer's arrival
 * moves content, not layout. The shapes are decoration, hidden from the
 * accessibility tree; the pulse rides `motion-safe:` so
 * prefers-reduced-motion stops it (F24), and the status line says what the
 * wait is.
 */
export function ShelfSkeleton() {
  return (
    <div aria-hidden="true" className="flex flex-col gap-8">
      <div className="flex flex-col justify-between gap-4 pb-1 lg:flex-row lg:items-end">
        <div className="flex flex-col gap-2">
          <div className="h-3 w-40 motion-safe:animate-pulse rounded-[var(--radius)] bg-rule" />
          <div className="h-8 w-64 motion-safe:animate-pulse rounded-[var(--radius)] bg-rule" />
          <div className="h-4 w-96 motion-safe:animate-pulse rounded-[var(--radius)] bg-rule" />
        </div>
        <div className="flex items-center gap-3">
          {[0, 1, 2].map((card) => (
            <div
              key={card}
              className="h-[66px] w-40 motion-safe:animate-pulse rounded-[var(--radius-surface)] bg-surface-container-low"
            />
          ))}
        </div>
      </div>
      <div className="flex flex-col items-center gap-8 rounded-[var(--radius-surface)] bg-surface-container-low p-6 md:flex-row lg:p-8">
        <div className="w-48 aspect-[3/4] motion-safe:animate-pulse rounded-[var(--radius)] bg-rule" />
        <div className="flex w-full flex-1 flex-col gap-3">
          <div className="h-4 w-56 motion-safe:animate-pulse rounded-[var(--radius)] bg-rule" />
          <div className="h-7 w-72 motion-safe:animate-pulse rounded-[var(--radius)] bg-rule" />
          <div className="h-4 w-full max-w-xl motion-safe:animate-pulse rounded-[var(--radius)] bg-rule" />
          <div className="h-4 w-2/3 motion-safe:animate-pulse rounded-[var(--radius)] bg-rule" />
          <div className="h-10 w-72 motion-safe:animate-pulse rounded-[var(--radius-control)] bg-rule" />
        </div>
      </div>
      <div className="flex items-center justify-between gap-3 pb-1">
        <div className="h-9 w-full motion-safe:animate-pulse rounded-[var(--radius-control)] bg-rule sm:w-72" />
        <div className="h-9 w-24 motion-safe:animate-pulse rounded-[var(--radius-control)] bg-rule" />
      </div>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((card) => (
          <div
            key={card}
            className="flex flex-col overflow-hidden rounded-[var(--radius-surface)] bg-surface-container-low"
          >
            <div className="flex items-center justify-center p-4">
              <div className="w-36 aspect-[3/4] motion-safe:animate-pulse rounded-[var(--radius)] bg-rule" />
            </div>
            <div className="flex flex-1 flex-col gap-2 p-4">
              <div className="h-5 w-2/3 motion-safe:animate-pulse rounded-[var(--radius)] bg-rule" />
              <div className="h-3 w-full motion-safe:animate-pulse rounded-[var(--radius)] bg-rule" />
              <div className="h-3 w-1/2 motion-safe:animate-pulse rounded-[var(--radius)] bg-rule" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** The wait's own voice: named, never a blank page, and never an empty
 *  library that has not heard yet. */
export function ShelfLoadingNotice() {
  const t = useTranslation();
  return (
    <Notice tone="quiet" live="status" className="mt-6">
      {t("novels.loading")}
    </Notice>
  );
}
