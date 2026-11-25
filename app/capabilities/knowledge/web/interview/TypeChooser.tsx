/**
 * The interview's first face (W9 Task 10): the type chooser. The writer picks
 * one of the contract's eight types — the type is fixed for the whole
 * interview and every question follows it — or takes the quiet second path
 * «Von Hand anlegen», which opens the existing create dialog. The type list
 * is the catalog's own order, the reference's 2×4 grid.
 */
import { useState } from "react";

import { useTranslation } from "@shell/lib/i18n";
import { FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import { entityTypeIcon, entityTypeLabel, typeTheme } from "../entityTypes";
import { ENTITY_TYPE_ORDER } from "./interviewState";

export function TypeChooser({
  onStart,
  onManual,
  starting,
  startFailed,
}: {
  onStart: (entityType: string) => void;
  onManual: () => void;
  starting: boolean;
  startFailed: boolean;
}) {
  const t = useTranslation();
  // Deliberately unselected (ruling 2026-11-25): no type is «the» default, so
  // «Interview starten» stays disabled until the writer picks one. The
  // illustrated tile preselects «Objekt»; that divergence is recorded in the
  // wave's gap ledger and must not be "fixed" toward the tile here.
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div className="flex min-h-0 flex-1 flex-col justify-between px-3 py-4">
      <div>
        <p className="mb-4 text-center text-title text-primary">{t("knowledge.interview.chooserQuestion")}</p>
        <div role="group" aria-label={t("knowledge.interview.chooserQuestion")} className="mb-4 grid grid-cols-2 gap-1.5">
          {ENTITY_TYPE_ORDER.map((type) => {
            const active = selected === type;
            const theme = typeTheme(type);
            return (
              <button
                key={type}
                type="button"
                data-testid={`entity-interview-type-${type}`}
                aria-pressed={active}
                onClick={() => setSelected(type)}
                className={`flex items-center gap-2 rounded-[var(--radius-control)] border p-2 text-left text-label transition-colors ${FOCUS} ${
                  active
                    ? "border-primary bg-secondary-container/40 font-semibold text-primary"
                    : "border-border bg-card text-foreground hover:bg-surface-container-low"
                }`}
              >
                <span className={`flex h-5 w-5 items-center justify-center rounded ${active ? theme.tint : ""}`} style={{ color: theme.var }}>
                  <Icon name={entityTypeIcon(type)} size={16} />
                </span>
                <span>{entityTypeLabel(t, type)}</span>
              </button>
            );
          })}
        </div>
        <p className="px-2 text-center text-[11px] leading-relaxed text-muted">
          {t("knowledge.interview.chooserHint")}
        </p>
      </div>
      <div className="mt-6 flex flex-col gap-2">
        {startFailed && (
          <p role="alert" className="rounded border border-danger/40 bg-panel px-2 py-1 text-meta text-danger">
            {t("knowledge.interview.startFailed")}
          </p>
        )}
        <button
          type="button"
          data-testid="entity-interview-start"
          disabled={selected === null || starting}
          onClick={() => {
            if (selected !== null) onStart(selected);
          }}
          className={`h-8 w-full rounded-[var(--radius-control)] bg-primary text-label font-semibold text-primary-foreground shadow-card transition-colors hover:opacity-95 disabled:cursor-not-allowed disabled:bg-surface-container disabled:text-muted ${FOCUS}`}
        >
          {t("knowledge.interview.start")}
        </button>
        <button
          type="button"
          data-testid="entity-interview-manual"
          onClick={onManual}
          className={`py-1 text-center text-meta text-muted transition-colors hover:text-primary ${FOCUS}`}
        >
          {t("knowledge.interview.manual")}
        </button>
      </div>
    </div>
  );
}
