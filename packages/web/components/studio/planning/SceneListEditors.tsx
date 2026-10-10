"use client";

import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ScenePresence } from "@/types/planning";

const INPUT_CLASS = "w-full px-2 py-1 bg-background border border-border rounded text-xs";
const ICON_BUTTON_CLASS =
  "p-0.5 rounded hover:bg-accent text-muted-foreground disabled:opacity-40 disabled:pointer-events-none";
const ADD_BUTTON_CLASS =
  "mt-1 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground";

interface BeatsEditorProps {
  beats: string[];
  onChange: (beats: string[]) => void;
}

/** String-list editor with add / remove / reorder-up / reorder-down per row. */
export function BeatsEditor({ beats, onChange }: BeatsEditorProps) {
  const t = useTranslations("studio.planning.scenes");

  function setItem(index: number, value: string) {
    onChange(beats.map((b, i) => (i === index ? value : b)));
  }

  function move(index: number, dir: -1 | 1) {
    const next = [...beats];
    const target = index + dir;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  }

  return (
    <div>
      <p className="text-xs font-medium mb-1">{t("beats")}</p>
      <ul className="space-y-1">
        {beats.map((beat, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: positional string rows; value keys would remount mid-typing
          <li key={`beat-${i}`} className="flex items-center gap-1">
            <input
              aria-label={t("beats")}
              value={beat}
              onChange={(e) => setItem(i, e.target.value)}
              className={INPUT_CLASS}
            />
            <button
              type="button"
              aria-label={t("moveBeatUp")}
              disabled={i === 0}
              onClick={() => move(i, -1)}
              className={ICON_BUTTON_CLASS}
            >
              <ArrowUp className="w-3 h-3" />
            </button>
            <button
              type="button"
              aria-label={t("moveBeatDown")}
              disabled={i === beats.length - 1}
              onClick={() => move(i, 1)}
              className={ICON_BUTTON_CLASS}
            >
              <ArrowDown className="w-3 h-3" />
            </button>
            <button
              type="button"
              aria-label={t("removeBeat")}
              onClick={() => onChange(beats.filter((_, j) => j !== i))}
              className={ICON_BUTTON_CLASS}
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        data-testid="add-beat-btn"
        onClick={() => onChange([...beats, ""])}
        className={ADD_BUTTON_CLASS}
      >
        <Plus className="w-3 h-3" /> {t("addBeat")}
      </button>
    </div>
  );
}

interface CharactersEditorProps {
  characters: ScenePresence[];
  onChange: (characters: ScenePresence[]) => void;
}

/** Present-character rows (name + goal) with add / remove. */
export function CharactersEditor({ characters, onChange }: CharactersEditorProps) {
  const t = useTranslations("studio.planning.scenes");

  function patchAt(index: number, part: Partial<ScenePresence>) {
    onChange(characters.map((c, i) => (i === index ? { ...c, ...part } : c)));
  }

  return (
    <div>
      <p className="text-xs font-medium mb-1">{t("characters")}</p>
      <ul className="space-y-1">
        {characters.map((character, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: positional rows in stage order; inputs are index-controlled
          <li key={`presence-${i}`} className="flex items-center gap-1">
            <input
              aria-label={t("characters")}
              value={character.name}
              placeholder={t("characters")}
              onChange={(e) => patchAt(i, { name: e.target.value })}
              className={INPUT_CLASS}
            />
            <input
              aria-label={t("characterGoal")}
              value={character.goal}
              placeholder={t("characterGoal")}
              onChange={(e) => patchAt(i, { goal: e.target.value })}
              className={INPUT_CLASS}
            />
            <button
              type="button"
              aria-label={t("removeCharacter")}
              onClick={() => onChange(characters.filter((_, j) => j !== i))}
              className={ICON_BUTTON_CLASS}
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={() => onChange([...characters, { id: null, name: "", goal: "" }])}
        className={ADD_BUTTON_CLASS}
      >
        <Plus className="w-3 h-3" /> {t("addCharacter")}
      </button>
    </div>
  );
}
