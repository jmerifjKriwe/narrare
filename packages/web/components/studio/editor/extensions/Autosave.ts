/**
 * Autosave — TipTap Extension for debounced content saving.
 *
 * Extracts autosave logic from EditorSurface into a reusable extension.
 * Debounces content changes and calls saveFn when content changes.
 * Exposes forceSave via storage for manual save triggers (Cmd+S).
 */

import { Extension } from "@tiptap/core";

export interface AutosaveOptions {
  interval: number;
  saveFn: (content: string) => Promise<void>;
  enabled: boolean;
}

export type SaveStatus = "idle" | "saving" | "saved" | "error";

interface AutosaveStorage {
  lastSavedContent: string;
  isSaving: boolean;
  saveStatus: SaveStatus;
  debounceTimer: ReturnType<typeof setTimeout> | null;
  forceSave: () => Promise<void>;
}

export const Autosave = Extension.create<AutosaveOptions, AutosaveStorage>({
  name: "autosave",

  addOptions() {
    return {
      interval: 30_000,
      saveFn: async () => {},
      enabled: true,
    };
  },

  addStorage() {
    return {
      lastSavedContent: "",
      isSaving: false,
      saveStatus: "idle" as SaveStatus,
      debounceTimer: null as ReturnType<typeof setTimeout> | null,
      forceSave: async () => {},
    };
  },

  onBeforeCreate() {
    // Bind forceSave to storage so external callers can trigger it
    this.storage.forceSave = async () => {
      const content = this.editor.getHTML();
      this.storage.isSaving = true;
      this.storage.saveStatus = "saving";
      try {
        await this.options.saveFn(content);
        this.storage.lastSavedContent = content;
        this.storage.saveStatus = "saved";
      } catch {
        this.storage.saveStatus = "error";
      } finally {
        this.storage.isSaving = false;
      }
    };
  },

  onUpdate() {
    if (!this.options.enabled) return;

    const content = this.editor.getHTML();
    if (content === this.storage.lastSavedContent) return;

    this.storage.saveStatus = "idle";

    if (this.storage.debounceTimer) {
      clearTimeout(this.storage.debounceTimer);
    }

    this.storage.debounceTimer = setTimeout(async () => {
      const current = this.editor.getHTML();
      if (current === this.storage.lastSavedContent) return;
      await this.storage.forceSave();
    }, this.options.interval);
  },

  onDestroy() {
    if (this.storage.debounceTimer) {
      clearTimeout(this.storage.debounceTimer);
    }
  },
});
