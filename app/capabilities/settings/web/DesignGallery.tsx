import { Button } from "@shell/ui/Button";
import { AREA_ICON } from "@shell/lib/area";
import { Cover, coverTone } from "@shell/ui/Cover";
import { Field, Select } from "@shell/ui/field";
import { GridList } from "@shell/ui/GridList";
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
 * the catalog (the six `design.*` keys for the page's own headings, already
 * landed keys for the specimens); the specimen labels themselves — token and
 * tone names — are documentation, the same in every language.
 *
 * The "Target" section pins the visual master every later slice builds
 * toward (atlas: spec §5.7, slot per family, fork decisions P1–P15). One
 * skeleton frame per slot family, each stamped ENTWURF and inert — `Row`
 * renders as `div` (no keyboard contract, no click), `Button` carries no
 * handler — so no frame pretends to work. The frame titles and their
 * P-notes are draft documentation in the record's language (German, like
 * §5.7's own fork reasons), the same in every locale; only the section
 * heading itself comes from the catalog. Fork pairs the atlas keeps as two
 * live homes — planning as Canvas vs Dock (P1/P2), knowledge graph as
 * canvas vs dock lens (P12) — render side by side with the decision note;
 * everywhere else a single draft, never decoration.
 *
 * The "Specimens" section pins the landed dock and palette states on the
 * real primitives — a conversation turn with its source chips, the
 * consistency card, the wrapped entity row, the palette dialog's button
 * row, the planning scene list — inert specimens, never embeds: no handlers, no fetches, no modal
 * shell. The subsection headings and source notes are documentation in
 * the record's language (German, like the draft titles), the same in
 * every locale; only the section heading itself comes from the catalog.
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
// The wrapped row's pin: a name no dock column can grow for, beside a
// short one — the row grows instead, wrapped, never truncated.
const ENTITY_SPECIMENS = [
  { id: "specimen-maya", name: "Maya Chen" },
  {
    id: "specimen-long",
    name: "Die Hüterin des Leuchtturms am Ende der Welt, die jedes verschwundene Schiff in ihr Ledger einträgt",
  },
];
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
            AREA_ICON map in lib/area — the one definition — which also keeps
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

      <section aria-labelledby="design-target-heading" className="mt-8">
        <h2 id="design-target-heading" className="text-emph font-semibold">
          {t("design.target")}
        </h2>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <Panel title="Planen-Canvas · Timeline-Landing (P1) · ENTWURF" titleAs="h3" dense>
            <Row as="div" flush>
              Kapitel 3 — Szene 12 · Ankommen
            </Row>
            <Row as="div" selected flush>
              Kapitel 3 — Szene 13 · Lücke
            </Row>
            <Row as="div" flush>
              Struktur — Akt II · Wendepunkt
            </Row>
            <div className="mt-2">
              <Notice tone="quiet">
                P1: Timeline statt Storyboard als Landing — die Zeitachse trägt
                Szene, Gap, Struktur und Arc; Storyboard bleibt Sibling-Canvas.
              </Notice>
            </div>
          </Panel>
          <Panel title="Planen-Dock · Szenen-Outline (P2) · ENTWURF" titleAs="h3" dense>
            <Row as="div" selected flush>
              Szene 12 — Ankommen
            </Row>
            <Row as="div" flush>
              Szene 13 — Lücke
            </Row>
            <Row as="div" flush>
              Arc — Maya: Zweifel
            </Row>
            <div className="mt-2">
              <Notice tone="quiet">
                P2: Dock statt Canvas — die Outline wird gegen den Text
                geschrieben; der Editor bleibt sichtbar.
              </Notice>
            </div>
          </Panel>
        </div>
        <div className="mt-3">
          <Panel title="Analysieren-Hub · Beta-Reader-Landing (P4) · ENTWURF" titleAs="h3" dense>
            <Row as="div" selected flush>
              Beta-Reader — Gesamtlesung
            </Row>
            <Row as="div" flush>
              Sentiment — Befund
            </Row>
            <Row as="div" flush>
              Readability — Score
            </Row>
            <Row as="div" flush>
              Literarische Suite — in der Canvas öffnen
            </Row>
            <div className="mt-2">
              <Notice tone="quiet">
                P4: Beta-Reader statt Metrik als Landing — einziger
                Autoren-Bericht, menschliches Gesicht des Hubs.
              </Notice>
            </div>
          </Panel>
        </div>
        <div className="mt-3">
          <Panel title="Analyse-Dock · geteilter Tab mit Switcher (P5) · ENTWURF" titleAs="h3" dense>
            <Row as="div" flush>
              Sentiment
            </Row>
            <Row as="div" flush>
              Readability
            </Row>
            <Row as="div" flush>
              POV-Brüche
            </Row>
            <Row as="div" selected flush>
              Plot-Befunde
            </Row>
            <div className="mt-2">
              <Notice tone="quiet">
                P5 + Kapazitätsregel: ein Tab „Analyse“, Befunde im Switcher —
                kein eigener Tab pro Bericht.
              </Notice>
            </div>
          </Panel>
        </div>
        <div className="mt-3">
          <Panel title="Analysieren-Canvas · Literarische Suite (P6) · ENTWURF" titleAs="h3" dense>
            <Row as="div" flush>
              Stil-Profil — Dichte und Rhythmus
            </Row>
            <Row as="div" selected flush>
              Motiv-Netz — wiederkehrende Bilder
            </Row>
            <Row as="div" flush>
              Stimmen-Vergleich — Erzähler gegen Figur
            </Row>
            <div className="mt-2">
              <Notice tone="quiet">
                P6: Canvas statt geteiltem Dock-Tab — mehrdimensionaler
                Bericht sprengt 352 px; einziger ANAL-Canvas neben dem Hub.
              </Notice>
            </div>
          </Panel>
        </div>
        <div className="mt-3">
          <Panel title="Schreiben-Dock · Multi-Draft-Sitzung (P7) · ENTWURF" titleAs="h3" dense>
            <Row as="div" selected flush>
              Variante A — gegen den Text
            </Row>
            <Row as="div" flush>
              Variante B
            </Row>
            <Row as="div" flush>
              Variante C — höchstens drei
            </Row>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button variant="primary">Übernehmen</Button>
              <Button variant="secondary">Verwerfen</Button>
            </div>
            <div className="mt-2">
              <Notice tone="quiet">
                P7: Dock statt Canvas — gewählt wird gegen den Text;
                „nebeneinander“ heißt Editor-Spalte + Dock, max. 3 Varianten.
              </Notice>
            </div>
          </Panel>
        </div>
        <div className="mt-3">
          <Panel title="Schreiben-Canvas · Serien-Verwaltung (P10) · ENTWURF" titleAs="h3" dense>
            <Row as="div" selected flush>
              Band-Verwaltung — Bände und Reihenfolge
            </Row>
            <Row as="div" flush>
              Serien-Bogen — übergreifende Handlung
            </Row>
            <div className="mt-2">
              <Notice tone="quiet">
                P10: Canvas statt neuer Nav-Area — bandübergreifende
                Verwaltung ist Shelf-nah; Einstieg via Shelf-Card, zu selten
                für eigenen Rail-Eintrag.
              </Notice>
            </div>
          </Panel>
        </div>
        <div className="mt-3">
          <Panel title="Schreiben-Canvas · Auswertung + Kosten-Reiter (P11) · ENTWURF" titleAs="h3" dense>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" size="sm">
                Leistung
              </Button>
              <Button variant="secondary" size="sm">
                Kosten
              </Button>
            </div>
            <div className="mt-2">
              <Row as="div" selected flush>
                Wortleistung — Verlauf 30 Tage
              </Row>
              <Row as="div" flush>
                Kosten — Tokens pro Lauf
              </Row>
            </div>
            <div className="mt-2">
              <Notice tone="quiet">
                P11: Kosten als Reiter der Stats-Canvas — gelesen neben der
                Leistung; Keys und Quotas bleiben in Settings, kein
                Doppel-Heim.
              </Notice>
            </div>
          </Panel>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <Panel title="Wissens-Canvas · Knowledge-Graph (KB-008) · ENTWURF" titleAs="h3" dense>
            <Row as="div" flush>
              Maya Chen — Figur
            </Row>
            <Row as="div" flush>
              Horizon Station — Ort
            </Row>
            <Row as="div" flush>
              ARIA — Figur
            </Row>
            <div className="mt-2">
              <Notice tone="quiet">
                P12: der Vollgraph lebt hier; die Dock-Linse linkt per
                Cross-Link hierher.
              </Notice>
            </div>
          </Panel>
          <Panel title="Wissen-Dock · Graph-Linse (P12) · ENTWURF" titleAs="h3" dense>
            <Row as="div" flush>
              Nachbarschaft — Szene 12
            </Row>
            <Row as="div" selected flush>
              Maya ↔ ARIA
            </Row>
            <div className="mt-2">
              <Notice tone="quiet">
                P12: Dock statt zweiter Canvas — lokale Linse neben der
                Selektion; „Im Graphen öffnen“ linkt zur Canvas.
              </Notice>
            </div>
          </Panel>
        </div>
        <div className="mt-3">
          <Panel title="Command-only · Paletten-Zeile + JobStatus · ENTWURF" titleAs="h3" dense>
            <Row as="div" flush>
              Umschreiben — Auswahl als Variante
            </Row>
            <Row as="div" flush>
              Ganzbuch-Check — Mehrschritt-Lauf
            </Row>
            <div className="mt-2">
              <Notice tone="quiet">
                Workflows, Inline-Vorschläge, Rewrite, Prompt-History:
                Command-Sequenz, Status via JobStatus (§5.5) — keine
                persistente Fläche.
              </Notice>
            </div>
          </Panel>
        </div>
        <div className="mt-3">
          <Panel title="Settings-Cluster · Regeln + Sync (P14/P15) · ENTWURF" titleAs="h3" dense>
            <Row as="div" flush>
              Konsistenz-Regel — Titel gegen Kapitel
            </Row>
            <Row as="div" flush>
              Extern-Sync — Zeitplan und Zugang
            </Row>
            <div className="mt-2">
              <Button variant="secondary">Jetzt synchronisieren</Button>
            </div>
            <div className="mt-2">
              <Notice tone="quiet">
                P14: Regel-CRUD ist Konfiguration — der CONS-001-Checker
                behält sein Dock. P15: Sync braucht Heim; der Button lebt auf
                dieser Seite, kein zweiter Slot.
              </Notice>
            </div>
          </Panel>
        </div>
        <div className="mt-3">
          <Panel title="Rail + Dock · erweiterte Zustände (6/7) · ENTWURF" titleAs="h3" dense>
            <Row as="div" flush>
              Home
            </Row>
            <Row as="div" flush>
              Planen
            </Row>
            <Row as="div" current flush>
              Analysieren
            </Row>
            <Row as="div" flush>
              Einstellungen
            </Row>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button variant="secondary" size="sm">
                Chat
              </Button>
              <Button variant="secondary" size="sm">
                Planen
              </Button>
              <Button variant="secondary" size="sm">
                Wissen
              </Button>
              <Button variant="secondary" size="sm">
                Analyse
              </Button>
              <Button variant="secondary" size="sm">
                Schreiben
              </Button>
            </div>
            <div className="mt-2">
              <Notice tone="quiet">
                Kapazitätsregel §5.7.2: Rail 6/7 — eine Reserve; Dock max. 6
                Tabs, der 7. Dock wird Switcher, nie zweite Reihe.
              </Notice>
            </div>
          </Panel>
        </div>
      </section>

      <section aria-labelledby="design-specimens-heading" className="mt-8">
        <h2 id="design-specimens-heading" className="text-emph font-semibold">
          {t("design.specimens")}
        </h2>
        <div className="mt-3">
          <h3 className="text-body font-semibold">
            Gesprächsrunde + Chips · Chat-Dock
          </h3>
          {/* The turn as ChatPanel renders it — question, answer, source
              chips — with one chip open on its quoted passage. Inert: no
              ask runs, no chip toggles; the expanded marks are the pin. */}
          <ol className="mt-2 flex flex-col gap-6">
            <li>
              <p className="text-label font-semibold">Woher kommt das Signal?</p>
              <p className="mt-2 whitespace-pre-wrap text-body leading-relaxed">
                Das Signal kommt aus Forschungsstation 7 in Nevada: die letzte
                Nachricht von Mayas Schwester, Jahre nach dem Unfall, der sie
                das Leben kostete.
              </p>
              <ul className="mt-2 flex flex-wrap gap-2">
                <li>
                  <Button variant="secondary" size="sm" aria-expanded="false">
                    Stationsnotizen
                  </Button>
                </li>
                <li>
                  <Button variant="secondary" size="sm" aria-expanded="true">
                    Zeitstrahl
                  </Button>
                  <p className="mt-1 whitespace-pre-wrap text-body leading-relaxed text-muted">
                    Drei Jahre vor dem Signal starb Mayas Schwester in
                    Forschungsstation 7; der Konzern nannte es einen Unfall.
                  </p>
                </li>
              </ul>
            </li>
          </ol>
          <div className="mt-2">
            <Notice tone="quiet">
              ChatPanel: eine Runde aus Frage, Antwort und Quellen-Chips; ein
              Chip steht offen auf seinem zitierten Beleg.
            </Notice>
          </div>
        </div>
        <div className="mt-3">
          <h3 className="text-body font-semibold">
            Konsistenzkarte · Wissen-Dock
          </h3>
          {/* The finding as ChecksPanel renders it: the Panel holds the
              finding as its heading and the evidence beneath, both decisions
              on shell Buttons. Inert: nothing acknowledges, nothing
              dismisses. */}
          <section aria-label={t("knowledge.findingTitle")} className="mt-2">
            <Panel>
              <h4 className="text-emph font-semibold">
                Forschungsstation: 7 gegen 9
              </h4>
              <p className="mt-2 whitespace-pre-wrap text-body leading-relaxed text-muted">
                Kapitel 1 nennt Forschungsstation 7, Kapitel 3 nennt
                Forschungsstation 9: ein Name mit zwei Nummern.
              </p>
              <div className="mt-3 flex gap-2">
                <Button>{t("proposal.accept")}</Button>
                <Button>{t("proposal.discard")}</Button>
              </div>
            </Panel>
          </section>
          <div className="mt-2">
            <Notice tone="quiet">
              ChecksPanel: der Befund als Karte mit Titel, Beleg und beiden
              Entscheidungen.
            </Notice>
          </div>
        </div>
        <div className="mt-3">
          <h3 className="text-body font-semibold">
            Umbrochene Entitätszeile · Wissen-Dock
          </h3>
          {/* The entity rows as EntitiesPanel renders them: the shell's
              selection list with the wrap the dock owns, so the long name
              grows the row instead of ellipsizing. Inert: no selection. */}
          <div className="mt-2">
            <GridList
              label={t("knowledge.entitiesHeading")}
              flush
              wrap
              items={ENTITY_SPECIMENS}
              getId={(entity) => entity.id}
              textOf={(entity) => entity.name}
              selectedId={null}
              onSelect={() => {}}
              render={(entity) => entity.name}
            />
          </div>
          <div className="mt-2">
            <Notice tone="quiet">
              EntitiesPanel: die Zeile bricht um, statt zu kürzen.
            </Notice>
          </div>
        </div>
        <div className="mt-3">
          <h3 className="text-body font-semibold">Dialogzeile · Palette</h3>
          {/* The consistency dialog's resting state: the trigger beside its
              cancel. The modal shell cannot stand inline in a gallery, so
              the row stands for it — the same two Buttons the dialog wears.
              Inert: no check enqueues, nothing closes. */}
          <div className="mt-2 flex flex-wrap gap-2">
            <Button variant="primary">{t("knowledge.checkNovel")}</Button>
            <Button variant="secondary">{t("knowledge.entityCancel")}</Button>
          </div>
          <div className="mt-2">
            <Notice tone="quiet">
              ConsistencyCheckDialog: die Paletten-Zeile
              Ganzes-Buch-prüfen öffnet diesen Dialog; ruhend ist er
              Auslöser neben Abbruch.
            </Notice>
          </div>
        </div>
        <div className="mt-3">
          <h3 className="text-body font-semibold">Szenenliste · Planen-Dock</h3>
          {/* The dock's built state: the chapter's scenes in order, each row
              with its title and status beside the advance it offers, one
              save for the whole list beside the add. Inert: no status
              advances, nothing saves, nothing is added. */}
          <section aria-label={t("planning.panelHeading")} className="mt-2">
            <ul className="flex flex-col">
              <li>
                <Row
                  as="div"
                  role="group"
                  aria-label="Ankommen"
                  flush
                  className="h-auto min-h-7 flex-col items-stretch gap-1 py-2"
                >
                  <span className="text-body">Ankommen</span>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-label text-muted">
                      {t("planning.status.planned")}
                    </span>
                    <Button variant="secondary" size="sm">
                      {t("planning.advanceStatus", {
                        status: t("planning.status.in_progress"),
                      })}
                    </Button>
                  </div>
                </Row>
              </li>
              <li>
                <Row
                  as="div"
                  role="group"
                  aria-label="Lücke"
                  flush
                  className="h-auto min-h-7 flex-col items-stretch gap-1 py-2"
                >
                  <span className="text-body">Lücke</span>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-label text-muted">
                      {t("planning.status.in_progress")}
                    </span>
                    <Button variant="secondary" size="sm">
                      {t("planning.advanceStatus", {
                        status: t("planning.status.complete"),
                      })}
                    </Button>
                  </div>
                </Row>
              </li>
            </ul>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button variant="primary">{t("planning.save")}</Button>
              <Button variant="secondary">{t("planning.addScene")}</Button>
            </div>
          </section>
          <div className="mt-2">
            <Notice tone="quiet">
              SceneDock: die Szenen des Kapitels in Reihenfolge mit Status;
              eine Speicherung gilt der ganzen Liste.
            </Notice>
          </div>
        </div>
      </section>
    </div>
  );
}
