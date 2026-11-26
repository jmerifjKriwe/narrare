// @vitest-environment jsdom
/**
 * The one save-status owner (W4 Task 12): the shell-level store the chrome's
 * sync surfaces read and the writing autosave hook writes. One vocabulary
 * (idle/saving/saved/failed), one face per state, never a disagreement between
 * the topbar chip, the rail foot and the editor foot. Task 10's static
 * „Gespeichert" interim ends here — the faces derive from the live state.
 */
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  SAVE_FACES,
  getSaveStatus,
  setSaveStatus,
  unsavedStatus,
  useSaveStatus,
} from "./saveStatus";
import { de } from "./test/catalogs";

afterEach(() => {
  cleanup();
  setSaveStatus("idle");
});

describe("the store", () => {
  it("rests at idle and takes the hook's writes", () => {
    expect(getSaveStatus()).toBe("idle");
    setSaveStatus("saving");
    expect(getSaveStatus()).toBe("saving");
    setSaveStatus("failed");
    expect(getSaveStatus()).toBe("failed");
    setSaveStatus("saved");
    expect(getSaveStatus()).toBe("saved");
  });

  it("the hook reads the live state and re-renders on a write", () => {
    const { result } = renderHook(() => useSaveStatus());
    expect(result.current).toBe("idle");
    act(() => setSaveStatus("saving"));
    expect(result.current).toBe("saving");
    act(() => setSaveStatus("failed"));
    expect(result.current).toBe("failed");
  });

  it("two subscribers agree — one state, three faces", () => {
    const a = renderHook(() => useSaveStatus());
    const b = renderHook(() => useSaveStatus());
    act(() => setSaveStatus("saving"));
    expect(a.result.current).toBe("saving");
    expect(b.result.current).toBe("saving");
  });
});

describe("unsavedStatus — the one question every guard asks", () => {
  it("saving and failed are unsaved; idle and saved are not", () => {
    expect(unsavedStatus("idle")).toBe(false);
    expect(unsavedStatus("saved")).toBe(false);
    expect(unsavedStatus("saving")).toBe(true);
    expect(unsavedStatus("failed")).toBe(true);
  });
});

describe("the faces — the chrome draft's three sync states (tile 3)", () => {
  it("idle and saved share the green Ruhe face", () => {
    for (const status of ["idle", "saved"] as const) {
      expect(SAVE_FACES[status].tone).toBe("success");
      expect(de[SAVE_FACES[status].label]).toBe("Gespeichert");
      expect(de[SAVE_FACES[status].note]).toBe(
        "Deine letzten Wörter sind automatisch in deiner Bibliothek gesichert.",
      );
    }
  });

  it("saving is the amber In-Arbeit face", () => {
    expect(SAVE_FACES.saving.tone).toBe("warning");
    expect(de[SAVE_FACES.saving.label]).toBe("Sicherung läuft …");
    expect(de[SAVE_FACES.saving.note]).toBe(
      "Die laufende Änderung wird gerade gesichert — kurz warten.",
    );
  });

  it("failed is the red Fehler face", () => {
    expect(SAVE_FACES.failed.tone).toBe("danger");
    expect(de[SAVE_FACES.failed.label]).toBe("Sicherung fehlgeschlagen");
    expect(de[SAVE_FACES.failed.note]).toBe(
      "Deine Änderungen bleiben im Editor, bis die Sicherung gelingt.",
    );
  });
});
