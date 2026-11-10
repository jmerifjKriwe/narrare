import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { SHORTCUTS, shortcutKeycap, type ShortcutScope } from "@shell/lib/shortcuts";
import { Row } from "@shell/ui/Row";

/** The group headings, in the order the page shows them. */
const SCOPE_TITLES: Record<ShortcutScope, MessageKey> = {
  global: "settings.shortcuts.global",
  workspace: "settings.shortcuts.workspace",
  editor: "settings.shortcuts.editor",
};

const SCOPES: ReadonlyArray<ShortcutScope> = ["global", "workspace", "editor"];

/**
 * The shortcuts cluster: the registry rendered read-only — one row per
 * binding, grouped by the scope it applies in, each with the platform's own
 * keycap. The rows are presentational (`Row as="div"`): there is nothing to
 * press, and remapping is explicitly not on offer yet (the note below says
 * so in one line — custom keybindings are out of this slice).
 */
export function ShortcutsPage() {
  const t = useTranslation();
  usePageTitle(t("settings.clusterShortcuts"));

  return (
    <section aria-labelledby="settings-shortcuts-heading">
      <h2 id="settings-shortcuts-heading" className="text-emph font-semibold">
        {t("settings.clusterShortcuts")}
      </h2>
      <p className="mt-1 text-body text-muted">{t("settings.shortcuts.note")}</p>
      {SCOPES.map((scope) => {
        const entries = SHORTCUTS.filter((entry) => entry.scope === scope);
        if (entries.length === 0) return null;
        return (
          <section key={scope} aria-labelledby={`settings-shortcuts-${scope}`} className="mt-6">
            <h3 id={`settings-shortcuts-${scope}`} className="text-body font-semibold">
              {t(SCOPE_TITLES[scope])}
            </h3>
            <div role="list" className="mt-2">
              {entries.map((entry) => (
                <Row
                  key={entry.id}
                  as="div"
                  role="listitem"
                  trailing={
                    <kbd className="rounded-[var(--radius)] border border-border bg-card px-1.5 py-0.5 font-mono text-meta leading-none text-muted">
                      {shortcutKeycap(entry.id)}
                    </kbd>
                  }
                >
                  <span className="min-w-0 flex-1">{t(entry.labelKey)}</span>
                </Row>
              ))}
            </div>
          </section>
        );
      })}
    </section>
  );
}
