/**
 * The AI-Regeln surface (W8 Task 9) — the settings capability's second
 * page, ported from the owner-approved harmonized `settings-ai-rules-2`
 * draft onto the shell's tokens, under the hub chrome (SettingsHub).
 *
 * The draft's geometry, in its order: the hero row with the pointer door
 * to the Buch-Einstellungen (ruling 1 — the Projekt-Regeln live there; the
 * door routes to the dialog's own deep link, the mirror of the W7
 * settings-side deep links the dialog itself retired), the segment pills
 * with their real counters, the three sections (Provider, Modelle,
 * Aufgaben), and the System-Diagnose block.
 *
 * Porting dispositions from the Stitch round's owner checkpoint — none of
 * these are omissions, they are the honest-state rules at work:
 * - No „Atelier Disziplin“ card and no footer: the card claims a
 *   Ghost-Buffer/[Tab] mechanic that does not exist, the footer's links
 *   lead nowhere — dead promises, both.
 * - The chat row's „0 Tok. (Offline)“ chip is not ported: the resolved
 *   number with the fake mark answers instead (the tasks read's own
 *   number).
 * - The hub's „Lokaler Speicher verifiziert“ chip is not ported: no read
 *   answers it.
 * - The providers' handshake/heartbeat faces are not ported: no read
 *   answers provider health.
 *
 * Honest page states: the loading skeleton while the five strict reads
 * stand, the outage face with its retry when any fails — never dressed-up
 * nulls, never a partial page that claims a configuration it could not see.
 */
import { Link } from "@tanstack/react-router";

import { SettingsHub } from "@shell/components/SettingsHub";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { queryClient, activeNovelFallback, useNovelsQuery } from "@shell/lib/query";
import { FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import { useAssignments, useModels, usePresets, useProviders } from "../aiRulesQuery";
import { useSettingsTasksQuery } from "../tasksQuery";
import { DiagnoseSection } from "./diagnoseSection";
import { ModelsSection } from "./modelsSection";
import { ProvidersSection } from "./providersSection";
import { TasksSection } from "./tasksSection";

const SERIF = "[font-family:var(--font-serif)]";

export function AiRulesPage() {
  const t = useTranslation();
  usePageTitle(t("settings.ai.pageTitle"));
  const providers = useProviders();
  const presets = usePresets();
  const models = useModels();
  const tasks = useSettingsTasksQuery();
  const assignments = useAssignments();

  // The pointer door's target: the active book (the chrome's own rule —
  // latest-edited, unarchived), read from the shell's own fallback. The
  // door hides while the read stands or fails, and states the why when no
  // book exists.
  const novels = useNovelsQuery();
  const activeNovel = novels.data !== undefined ? activeNovelFallback(novels.data) : null;

  const reads = [providers, presets, models, tasks, assignments];
  // The conjunction of the answers themselves, not the isSuccess flags: the
  // data is what the sections consume, and this conjunction narrows the
  // `| undefined` away for the compiler as it gates the render.
  const data =
    providers.data !== undefined &&
    presets.data !== undefined &&
    models.data !== undefined &&
    tasks.data !== undefined &&
    assignments.data !== undefined
      ? { providers: providers.data, presets: presets.data, models: models.data, tasks: tasks.data, assignments: assignments.data }
      : null;

  /** The retry re-asks every read that answered nothing — the outage face's
   *  own door, applied to the page's whole family, the driver read's word
   *  included (the diagnose card hides on its failure; the retry recovers
   *  it too). */
  function retry() {
    for (const read of reads) {
      if (read.isError) void read.refetch();
    }
    // A read that never mounted its ask (an earlier throw left it idle)
    // re-asks through the cache invalidation.
    void queryClient.invalidateQueries({ queryKey: ["settings-providers"] });
    void queryClient.invalidateQueries({ queryKey: ["settings-presets"] });
    void queryClient.invalidateQueries({ queryKey: ["settings-models"] });
    void queryClient.invalidateQueries({ queryKey: ["settings-tasks"] });
    void queryClient.invalidateQueries({ queryKey: ["settings-assignments"] });
    void queryClient.invalidateQueries({ queryKey: ["settings-driver"] });
  }

  return (
    <main id="main-content" data-testid="ai-rules-page" aria-busy={data === null} className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-8 px-8 py-10 pb-24">
        <SettingsHub />

        {/* Hero & the pointer door. */}
        <section className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl space-y-2">
            <div className="flex items-center gap-2 uppercase tracking-wider text-muted text-eyebrow">
              <span>{t("settings.ai.eyebrow")}</span>
              <span aria-hidden="true" className="h-1 w-1 rounded-full bg-muted opacity-50" />
              <span>{t("settings.ai.eyebrowBrand")}</span>
            </div>
            <h1 className={`${SERIF} text-hero font-normal tracking-tight text-foreground`}>
              {t("settings.ai.heading")}
            </h1>
            <p className="max-w-xl text-body leading-relaxed text-muted">{t("settings.ai.subtitle")}</p>
          </div>

          {/* The pointer door (ruling 1): the Buch-Einstellungen live in the
              book's workspace; the deep link opens the dialog there — the
              same hash mechanism the dialog's own settings door used, in the
              other direction. No book: the why, stated — never a dead door. */}
          {novels.data !== undefined && activeNovel !== null ? (
            <Link
              to="/novels/$novelId"
              params={{ novelId: activeNovel.id }}
              hash="buch-einstellungen"
              data-testid="pointer-door"
              className={`group flex max-w-md items-center gap-3 rounded-lg border border-border bg-surface p-3.5 shadow-sm transition-colors hover:bg-surface-container ${FOCUS}`}
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded bg-cover-sepia/10 text-primary">
                <Icon name="autoStories" size={20} />
              </span>
              <span className="flex min-w-0 flex-col pr-2">
                <span className="truncate text-label font-semibold text-foreground transition-colors group-hover:text-primary">
                  {t("settings.ai.pointer.title")}
                </span>
                <span className="truncate text-meta text-muted">{t("settings.ai.pointer.body")}</span>
              </span>
              <span className="text-muted transition-transform group-hover:translate-x-0.5">
                <Icon name="arrowRight" size={18} />
              </span>
            </Link>
          ) : novels.data !== undefined ? (
            <div
              data-testid="pointer-door-none"
              className="max-w-md rounded-lg border border-border bg-panel p-3.5 text-meta text-muted"
            >
              {t("settings.ai.pointer.none")}
            </div>
          ) : null}
        </section>

        {reads.some((read) => read.isError) ? (
          /* The outage: named, with the retry — never dressed-up nulls. */
          <div className="flex justify-center p-6">
            <div role="alert" className="space-y-2 rounded-lg border border-danger/40 bg-panel p-5 text-center">
              <p className="text-body text-danger">{t("settings.loadFailed")}</p>
              <button
                type="button"
                onClick={retry}
                className={`rounded border border-border bg-surface-container-low px-3 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
              >
                {t("settings.retry")}
              </button>
            </div>
          </div>
        ) : data === null ? (
          /* The loading skeleton: the honest line, the draft's column. */
          <div className="space-y-6" role="status">
            <p className="text-body text-muted">{t("settings.loading")}</p>
            <div aria-hidden="true" className="space-y-3">
              <div className="h-10 w-72 animate-pulse rounded bg-soft" />
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="h-44 animate-pulse rounded bg-soft" />
                <div className="h-44 animate-pulse rounded bg-soft" />
              </div>
              <div className="h-64 animate-pulse rounded bg-soft" />
            </div>
          </div>
        ) : data !== null ? (
          <>
            {/* Segment pills with the real counters. */}
            <nav aria-label={t("settings.ai.nav.label")} className="flex flex-wrap items-center gap-2 pt-2">
              <a
                href="#sektion-provider"
                className={`inline-flex items-center gap-1.5 rounded bg-panel px-3 py-1.5 text-label text-muted shadow-sm transition-colors hover:bg-soft hover:text-foreground ${FOCUS}`}
              >
                <span>{t("settings.ai.nav.providers", { count: data.providers.length })}</span>
              </a>
              <a
                href="#sektion-modelle"
                className={`inline-flex items-center gap-1.5 rounded bg-panel px-3 py-1.5 text-label text-muted shadow-sm transition-colors hover:bg-soft hover:text-foreground ${FOCUS}`}
              >
                <span>{t("settings.ai.nav.models", { count: data.models.length })}</span>
              </a>
              <a
                href="#sektion-aufgaben"
                className={`inline-flex items-center gap-1.5 rounded bg-panel px-3 py-1.5 text-label text-muted shadow-sm transition-colors hover:bg-soft hover:text-foreground ${FOCUS}`}
              >
                <span>{t("settings.ai.nav.assignments", { count: data.assignments.length })}</span>
              </a>
              <a
                href="#sektion-diagnose"
                className={`inline-flex items-center gap-1.5 rounded bg-panel px-3 py-1.5 text-label text-muted shadow-sm transition-colors hover:bg-soft hover:text-foreground ${FOCUS}`}
              >
                <span>{t("settings.ai.nav.diagnose")}</span>
              </a>
            </nav>

            <ProvidersSection providers={data.providers} presets={data.presets} />
            <ModelsSection
              models={data.models}
              providers={data.providers}
              presets={data.presets}
              assignments={data.assignments}
            />
            <TasksSection tasks={data.tasks} assignments={data.assignments} models={data.models} />
            <DiagnoseSection models={data.models} />
          </>
        ) : null}
      </div>
    </main>
  );
}
