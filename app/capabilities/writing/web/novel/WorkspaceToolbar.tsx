import { docks } from "@shell/lib/generated/docks";
import { useTranslation } from "@shell/lib/i18n";
import { Button } from "@shell/ui/Button";
import { Field, Input } from "@shell/ui/field";
import { Icon } from "@shell/ui/icons";

import type { FocusStep } from "../routes";

type DockRow = (typeof docks)[number];

export function WorkspaceToolbar({
  focus,
  collapsed,
  showRail,
  pending,
  failed,
  chapterCount,
  railFilter,
  activeDockPath,
  step,
  toggleRail,
  toggleDock,
  setWalkedIndex,
  setRailFilter,
}: {
  focus: FocusStep;
  collapsed: boolean;
  showRail: boolean;
  pending: boolean;
  failed: boolean;
  chapterCount: number;
  railFilter: string | null;
  activeDockPath: string | undefined;
  step: (next: FocusStep) => void;
  toggleRail: () => void;
  toggleDock: (dock: DockRow) => void;
  setWalkedIndex: (value: number | null) => void;
  setRailFilter: (value: string | null) => void;
}) {
  const t = useTranslation();
  return (
    <div className="mt-6 flex flex-wrap items-center gap-2">
      {/* The band wraps before it overflows: a phone's 328 px content
          box cannot hold four icon buttons and an input's automatic
          minimum on one line, and the field is `min-w-0` so it shrinks
          into the space the buttons leave (or takes a line of its own)
          instead of pushing the page's gutter aside. */}
      <Button
        variant="icon"
        icon={<Icon name="focus" />}
        label={t("workspace.focusToggle")}
        aria-pressed={focus > 0}
        onClick={() => step(focus === 0 ? 1 : 0)}
      />
      {focus === 0 ? (
        <Button
          variant="icon"
          icon={<Icon name={collapsed ? "railShow" : "railHide"} />}
          label={t("workspace.railToggle")}
          aria-pressed={collapsed}
          onClick={toggleRail}
        />
      ) : null}
      <div role="group" aria-label={t("workspace.dockToggle")} className="flex items-center gap-2">
        {docks.map((dock) => (
          <Button
            key={dock.id}
            variant="icon"
            icon={<Icon name={dock.id} />}
            label={t(dock.titleKey)}
            aria-pressed={activeDockPath === dock.path}
            onClick={() => toggleDock(dock)}
          />
        ))}
      </div>
      {/* The rail's filter (Task 12): the long rail's own field, in the
          band that already holds the rail's collapse control. It stands
          only above twenty chapters and only while the rail itself is
          on screen — a field for a hidden list would be a promise with
          no subject. The input's accessible name is the fuller phrase
          that carries the visible label inside it, so the name a reader
          hears says what the field matches. */}
      {focus === 0 && showRail && !pending && !failed && chapterCount > 20 ? (
        <Field label={t("chapters.railFilter")} className="ml-auto w-40 min-w-0">
          <Input
            type="search"
            value={railFilter ?? ""}
            onChange={(event) => {
              const value = event.target.value;
              // The walk ends with the question: its row may no longer
              // be in the list the next answer renders, and a stale
              // index would leave that list without a tab stop.
              setWalkedIndex(null);
              setRailFilter(value.trim() === "" ? null : value);
            }}
            aria-label={t("chapters.railFilterAria")}
            className="min-w-0"
          />
        </Field>
      ) : null}
    </div>
  );
}
