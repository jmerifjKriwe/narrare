import { useTranslation } from "@shell/lib/i18n";
import { Button } from "@shell/ui/Button";
import { Icon } from "@shell/ui/icons";

/**
 * The empty shelf (`screens/library/shelf-empty.html`): not a dead end
 * but the drafted invitation — the unwritten book as a composed sepia
 * object, the serif promise beside it, the two doors under it, and the
 * formats line at its foot. The two blurred glows behind it are the
 * panel's own parchment light.
 */

/** The decorative unwritten book: the empty screen's own composed cover —
 *  the sepia ground, the wide spine, the bookmark tab, the dashed sheet
 *  waiting in its centre. Real text, no art: forced colours keep it a
 *  labelled object even without its palette. */
function UnwrittenCover() {
  const t = useTranslation();
  return (
    <div
      aria-hidden="true"
      className="relative my-6 w-48 aspect-[3/4] shrink-0 overflow-hidden rounded-r-lg rounded-l-sm border-r border-t border-b border-white/10 bg-cover-sepia p-5 text-cover-sepia-ink shadow-[var(--shadow-card)]"
    >
      <div className="absolute inset-y-0 left-0 w-4 bg-gradient-to-r from-black/45 via-white/15 to-transparent" />
      <div className="absolute top-0 right-8 h-14 w-4 rounded-b-sm border-b border-primary/20 bg-secondary-container shadow-[var(--shadow-card)]" />
      <div className="relative z-10 pl-2 text-left">
        <span className="mb-1 block text-eyebrow uppercase">{t("shelf.empty.edition")}</span>
        <div className="mb-3 h-0.5 w-8 bg-focus/80" />
        <span className="block text-meta italic">{t("shelf.empty.unwritten")}</span>
      </div>
      <div className="relative z-10 my-auto flex flex-col items-center justify-center self-center pl-2 opacity-85">
        <div className="grid h-14 w-14 place-items-center rounded-full border border-dashed border-current">
          <Icon name="autoStories" />
        </div>
        <span className="mt-2 text-eyebrow uppercase">{t("shelf.empty.sheet")}</span>
      </div>
      <div className="relative z-10 flex items-center justify-between pl-2">
        <span className="text-meta">{t("shelf.empty.atelier")}</span>
        {/* The drafts' quill has no glyph in the set; the pen is the set's
         * own word for it (deviation #1: drafted glyphs name concepts). */}
        <Icon name="write" />
      </div>
    </div>
  );
}

/** The drafted empty panel: the cover, the copy, the two doors. */
export function EmptyShelf({
  onCreate,
  onImport,
}: {
  onCreate: () => void;
  onImport: () => void;
}) {
  const t = useTranslation();
  return (
    <section className="relative flex flex-col items-center justify-center overflow-hidden rounded-[var(--radius-surface)] border border-rule bg-surface-container-low p-6 text-center shadow-[var(--shadow-card)] lg:p-8">
      <div className="pointer-events-none absolute -top-24 -left-24 h-80 w-80 rounded-full bg-cover-sepia opacity-5 blur-3xl" />
      <div className="pointer-events-none absolute -right-24 -bottom-24 h-80 w-80 rounded-full bg-primary opacity-5 blur-3xl" />
      <div className="group relative transition-transform duration-300 hover:-translate-y-1">
        <UnwrittenCover />
      </div>
      <div className="relative z-10 max-w-xl space-y-3">
        <h2 className="prose-headline">
          {t("shelf.empty.title")}
        </h2>
        <p className="text-[18px] leading-[31.5px] text-muted [font-family:'EB_Garamond',Georgia,'Times_New_Roman',serif]">
          {t("shelf.empty.body")}
        </p>
      </div>
      <div className="relative z-10 flex flex-wrap items-center justify-center gap-3 pt-4">
        <Button variant="primary" size="lg" icon={<Icon name="plus" />} onClick={onCreate}>
          {t("novels.new")}
        </Button>
        <Button variant="secondary" size="lg" icon={<Icon name="import" />} onClick={onImport}>
          {t("shelf.empty.importManuscript")}
        </Button>
      </div>
      <div className="relative z-10 pt-4 text-center">
        <p className="flex items-center justify-center gap-1.5 text-meta text-muted">
          <span className="text-outline" aria-hidden="true">
            <Icon name="checkCircle" />
          </span>
          {t("shelf.empty.formats")}
        </p>
      </div>
    </section>
  );
}
