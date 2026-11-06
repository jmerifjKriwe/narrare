import { Button } from "@shell/ui/Button";
import { AREA_ICON } from "@shell/components/IconRail";
import { Cover, coverTone } from "@shell/ui/Cover";
import { Field, Select } from "@shell/ui/field";
import { Notice } from "@shell/ui/Notice";
import { Panel } from "@shell/ui/Panel";
import { Row } from "@shell/ui/Row";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";

/**
 * The living design gallery: every shared primitive and token in one place,
 * for review and screenshots. Root-parented at `/design` — outside the
 * settings hub's clusters, nav and user docs — so gates and humans reach it
 * by URL while the product never points at it.
 *
 * The gallery shows only the real primitives (`Button`, `Field`+`Select`,
 * `Notice`, `Cover`, `Row`, `Panel`) and the shell's token utilities: no new
 * CSS, no new token, no new component. The words a control needs come from
 * the catalog (the five `design.*` keys for the page's own headings, already
 * landed keys for the specimens); the specimen labels themselves — token and
 * tone names — are documentation, the same in every language.
 */

// The cover's three tones, pinned like Cover.test pins them: the tone is a
// pure hash of the title, so these names keep their tone.
const PALE_TITLE = "Das Zählwerk";
const SEPIA_TITLE = "Gegenwind";
const INK_TITLE = "Der Sturm";

// The clamp's pin: a title no rail geometry can fit. The wrapper carries the
// pin attributes — `Cover` takes no extra props — and names the tone the
// title hashes to, so the pin and the tile cannot disagree.
const LONG_TITLE = "A".repeat(120);
const TONE_NAMES = ["pale", "sepia", "ink"] as const;

const TYPE_STEPS = [
  "text-meta",
  "text-label",
  "text-body",
  "text-emph",
  "text-title",
  "text-hero",
] as const;

export function DesignGallery() {
  const t = useTranslation();
  usePageTitle(t("design.heading"));

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-title font-semibold tracking-tight">{t("design.heading")}</h1>

      <section aria-labelledby="design-tokens-heading" className="mt-8">
        <h2 id="design-tokens-heading" className="text-emph font-semibold">
          {t("design.tokens")}
        </h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <span aria-hidden="true" className="border border-border bg-card px-2 py-1 text-label">
            bg-card
          </span>
          <span aria-hidden="true" className="border border-border bg-panel px-2 py-1 text-label">
            bg-panel
          </span>
          <span aria-hidden="true" className="border border-border bg-soft px-2 py-1 text-label">
            bg-soft
          </span>
          <span aria-hidden="true" className="border border-border bg-background px-2 py-1 text-label">
            bg-background
          </span>
          <span aria-hidden="true" className="border border-border bg-primary px-2 py-1 text-label text-primary-foreground">
            bg-primary
          </span>
        </div>
        <div className="mt-3 flex flex-col gap-1">
          <p className="text-body text-foreground">text-foreground</p>
          <p className="text-body text-muted">text-muted</p>
          <p className="text-body text-success">text-success</p>
          <p className="text-body text-warning">text-warning</p>
          <p className="text-body text-danger">text-danger</p>
        </div>
        {/* Rail-icon-sized swatches: the cover grounds and the area hues live
            on objects and nav icons, never as fills or text elsewhere, so the
            gallery shows them only at that small size. The hues come from the
            rail's own AREA_ICON map — the one definition — which also keeps
            the type-scale census (area hues stay in the rail) green. */}
        <div className="mt-3 flex items-center gap-2">
          <span aria-hidden="true" className="inline-block size-4 bg-cover-pale" />
          <span aria-hidden="true" className="inline-block size-4 bg-cover-sepia" />
          <span aria-hidden="true" className="inline-block size-4 bg-cover-ink" />
          <span aria-hidden="true" className={`inline-block size-4 ${AREA_ICON.writing}`}>
            ■
          </span>
          <span aria-hidden="true" className={`inline-block size-4 ${AREA_ICON.knowledge}`}>
            ■
          </span>
          <span aria-hidden="true" className={`inline-block size-4 ${AREA_ICON.chat}`}>
            ■
          </span>
          <span aria-hidden="true" className={`inline-block size-4 ${AREA_ICON.settings}`}>
            ■
          </span>
        </div>
      </section>

      <section aria-labelledby="design-type-heading" className="mt-8">
        <h2 id="design-type-heading" className="text-emph font-semibold">
          {t("design.type")}
        </h2>
        <div className="mt-3 flex flex-col gap-1">
          {TYPE_STEPS.map((step) => (
            <p key={step} className={step}>
              {step}
            </p>
          ))}
        </div>
      </section>

      <section aria-labelledby="design-controls-heading" className="mt-8">
        <h2 id="design-controls-heading" className="text-emph font-semibold">
          {t("design.controls")}
        </h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button variant="primary">{t("proposal.accept")}</Button>
          <Button variant="secondary">{t("proposal.discard")}</Button>
          <Button variant="ghost">{t("settings.retry")}</Button>
        </div>
        <div className="mt-3 max-w-64">
          <Field label={t("settings.appearance.themeLabel")} hint={t("settings.appearance.hint")}>
            <Select defaultValue="system">
              <option value="system">{t("settings.appearance.system")}</option>
              <option value="light">{t("settings.appearance.light")}</option>
              <option value="dark">{t("settings.appearance.dark")}</option>
            </Select>
          </Field>
        </div>
        <div className="mt-3 flex flex-col gap-2">
          <Notice tone="info">{t("settings.appearance.hint")}</Notice>
          <Notice tone="warning">{t("knowledge.modelChanged")}</Notice>
          <Notice tone="danger">{t("settings.appearance.errorSave")}</Notice>
          <Notice tone="quiet">{t("settings.clusterAppearance.description")}</Notice>
        </div>
      </section>

      <section aria-labelledby="design-surfaces-heading" className="mt-8">
        <h2 id="design-surfaces-heading" className="text-emph font-semibold">
          {t("design.surfaces")}
        </h2>
        <div className="mt-3">
          <Panel title={t("settings.assignments")}>
            <Row as="div" flush>
              {t("settings.task.writing.continuation")}
            </Row>
            <Row as="div" selected flush>
              {t("settings.task.chat.ask")}
            </Row>
            <Row as="div" current flush>
              {t("settings.task.knowledge.extract-entities")}
            </Row>
          </Panel>
        </div>
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <Cover title={PALE_TITLE} />
          <Cover title={SEPIA_TITLE} />
          <Cover title={INK_TITLE} />
          {/* The clamp's pin (see LONG_TITLE): the utility class is the real
              styling; the inline declaration is for jsdom, which runs no
              Tailwind cascade, so `getComputedStyle` only sees inline style. */}
          <div
            data-cover-tone={TONE_NAMES[coverTone(LONG_TITLE)]}
            data-long-title
            className="overflow-hidden"
            style={{ overflow: "hidden" }}
          >
            <Cover title={LONG_TITLE} />
          </div>
        </div>
      </section>
    </div>
  );
}
