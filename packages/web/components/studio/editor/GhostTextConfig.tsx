"use client";

import type { Editor } from "@tiptap/react";
import { Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { GhostTextStorage } from "./extensions/GhostText";

// ── Types ──────────────────────────────────────────────────────────────────────

interface GhostTextConfigProps {
  readonly editor: Editor | null;
}

// ── Constants ──────────────────────────────────────────────────────────────────

const STORAGE_KEY_ENABLED = "ghostText.enabled";
const STORAGE_KEY_DELAY = "ghostText.delay";
const DELAY_MIN = 500;
const DELAY_MAX = 2000;
const DELAY_STEP = 100;
const DEFAULT_DELAY = 800;

// ── Helpers ────────────────────────────────────────────────────────────────────

function readStoredBoolean(key: string, fallback: boolean): boolean {
  if (typeof window === "undefined") return fallback;
  const raw = localStorage.getItem(key);
  if (raw === null) return fallback;
  return raw !== "false";
}

function readStoredNumber(key: string, fallback: number): number {
  if (typeof window === "undefined") return fallback;
  const raw = localStorage.getItem(key);
  if (raw === null) return fallback;
  const parsed = Number(raw);
  return Number.isNaN(parsed) ? fallback : parsed;
}

// ── Component ──────────────────────────────────────────────────────────────────

/**
 * GhostTextConfig — toolbar control for the Ghost Text extension.
 *
 * Provides:
 * - Toggle button to enable/disable ghost text suggestions
 * - Slider to adjust the trigger delay (500ms–2000ms)
 *
 * Preferences are persisted in localStorage and synced to the TipTap
 * extension storage on change.
 */
export function GhostTextConfig({ editor }: GhostTextConfigProps) {
  const t = useTranslations("editor");

  const [enabled, setEnabled] = useState(() => readStoredBoolean(STORAGE_KEY_ENABLED, true));
  const [delay, setDelay] = useState(() => readStoredNumber(STORAGE_KEY_DELAY, DEFAULT_DELAY));

  // Sync state → extension storage whenever values change
  useEffect(() => {
    if (!editor || editor.isDestroyed) return;
    // TipTap's Editor.storage is typed as an empty interface; cast to access extensions.
    const extStorage = editor.storage as unknown as Record<string, unknown>;
    const storage = extStorage.ghostText as GhostTextStorage | undefined;
    if (!storage?.setEnabled || !storage?.setDelay) return;
    storage.setEnabled(enabled);
    storage.setDelay(delay);
  }, [editor, enabled, delay]);

  const handleToggle = useCallback(() => {
    const next = !enabled;
    setEnabled(next);
    localStorage.setItem(STORAGE_KEY_ENABLED, String(next));
  }, [enabled]);

  const handleDelayChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = Number(e.target.value);
    setDelay(value);
    localStorage.setItem(STORAGE_KEY_DELAY, String(value));
  }, []);

  return (
    <fieldset
      className="flex items-center gap-3 border-0 p-0 m-0"
      aria-label={t("ghostTextToggle")}
    >
      {/* Toggle button */}
      <button
        type="button"
        onClick={handleToggle}
        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
          enabled
            ? "bg-primary/10 text-primary"
            : "bg-accent text-muted-foreground hover:text-foreground"
        }`}
        title={enabled ? t("ghostTextEnabled") : t("ghostTextDisabled")}
        aria-pressed={enabled}
      >
        <Sparkles className="w-3.5 h-3.5" />
        <span>{t("ghostTextToggle")}</span>
      </button>

      {/* Delay slider (visible only when enabled) */}
      {enabled && (
        <div className="flex items-center gap-2">
          <label
            htmlFor="ghost-text-delay"
            className="text-xs text-muted-foreground whitespace-nowrap"
          >
            {t("ghostTextDelay")}
          </label>
          <input
            id="ghost-text-delay"
            type="range"
            min={DELAY_MIN}
            max={DELAY_MAX}
            step={DELAY_STEP}
            value={delay}
            onChange={handleDelayChange}
            className="w-20 h-1.5 accent-primary cursor-pointer"
          />
          <span className="text-xs text-muted-foreground tabular-nums min-w-[3rem]">
            {t("ghostTextDelayValue", { value: delay })}
          </span>
        </div>
      )}
    </fieldset>
  );
}
