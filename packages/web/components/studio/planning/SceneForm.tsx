"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { useRefineScene } from "@/lib/hooks/usePlanning";
import type { ScenePlan, SceneRef, SceneStatus } from "@/types/planning";
import { BeatsEditor, CharactersEditor } from "./SceneListEditors";

interface SceneFormProps {
  scene: ScenePlan;
  novelId: string;
  chapterId: string;
  onChange: (next: ScenePlan) => void;
}

const STATUS_OPTIONS: ReadonlyArray<{ value: SceneStatus; labelKey: string }> = [
  { value: "planned", labelKey: "statusPlanned" },
  { value: "in_progress", labelKey: "statusInProgress" },
  { value: "complete", labelKey: "statusComplete" },
];

const INPUT_CLASS = "w-full px-2 py-1 bg-background border border-border rounded text-xs";

/** Labelled field shell — keeps the form rows uniform (label text via i18n). */
function Field({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="text-xs font-medium block mb-1">
        {label}
      </label>
      {children}
    </div>
  );
}

/** Empty name clears the ref; empty id makes it a name-only ref. */
const refFromInputs = (name: string, id: string): SceneRef | null =>
  name.trim() ? { id: id.trim() || null, name: name.trim() } : null;

interface RefFieldProps {
  id: string;
  label: string;
  idLabel: string;
  value: SceneRef | null;
  onChange: (next: SceneRef | null) => void;
}

/** One hybrid-ref editor: labelled name input + optional id input. */
function RefField({ id, label, idLabel, value, onChange }: RefFieldProps) {
  const nameId = `${id}-name`;
  return (
    <Field id={nameId} label={label}>
      <input
        id={nameId}
        value={value?.name ?? ""}
        onChange={(e) => onChange(refFromInputs(e.target.value, value?.id ?? ""))}
        className={INPUT_CLASS}
      />
      <input
        aria-label={idLabel}
        value={value?.id ?? ""}
        onChange={(e) => onChange(refFromInputs(value?.name ?? "", e.target.value))}
        className={`${INPUT_CLASS} mt-1`}
      />
    </Field>
  );
}

/** Scene field editor — edits stay LOCAL (the caller decides when to save). */
export function SceneForm({ scene, novelId, chapterId, onChange }: SceneFormProps) {
  const t = useTranslations("studio.planning.scenes");
  const refine = useRefineScene(novelId);
  const [instruction, setInstruction] = useState("");
  // Latest-scene mirror: mid-flight refine calls must not revert typed edits.
  const sceneRef = useRef(scene);
  useEffect(() => {
    sceneRef.current = scene;
  }, [scene]);

  const patch = (part: Partial<ScenePlan>) => onChange({ ...scene, ...part });
  const fieldId = (suffix: string) => `scene-${scene.id}-${suffix}`;

  function handleRefine() {
    const vars = { chapterId, body: { scene, instruction: instruction.trim() || undefined } };
    refine.mutate(vars, {
      onSuccess: (res) => {
        if (res.ai_unavailable || !res.proposal) return;
        // Merge over the LATEST scene; identity/status/timestamps stay intact.
        onChange({ ...sceneRef.current, ...res.proposal });
      },
    });
  }

  return (
    <div className="space-y-2 p-2 border border-border rounded-md bg-muted/30">
      <Field id={fieldId("title")} label={t("sceneTitle")}>
        <input
          id={fieldId("title")}
          value={scene.title}
          onChange={(e) => patch({ title: e.target.value })}
          className={INPUT_CLASS}
        />
      </Field>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <RefField
          id={fieldId("pov")}
          label={t("pov")}
          idLabel={t("povId")}
          value={scene.pov_character_ref}
          onChange={(pov_character_ref) => patch({ pov_character_ref })}
        />
        <RefField
          id={fieldId("location")}
          label={t("location")}
          idLabel={t("locationId")}
          value={scene.location_ref}
          onChange={(location_ref) => patch({ location_ref })}
        />
      </div>

      <Field id={fieldId("purpose")} label={t("purpose")}>
        <textarea
          id={fieldId("purpose")}
          value={scene.purpose}
          onChange={(e) => patch({ purpose: e.target.value })}
          rows={2}
          className={`${INPUT_CLASS} resize-y`}
        />
      </Field>
      <Field id={fieldId("conflict")} label={t("conflict")}>
        <textarea
          id={fieldId("conflict")}
          value={scene.conflict}
          onChange={(e) => patch({ conflict: e.target.value })}
          rows={2}
          className={`${INPUT_CLASS} resize-y`}
        />
      </Field>
      <Field id={fieldId("resolution")} label={t("resolution")}>
        <textarea
          id={fieldId("resolution")}
          value={scene.resolution}
          onChange={(e) => patch({ resolution: e.target.value })}
          rows={2}
          className={`${INPUT_CLASS} resize-y`}
        />
      </Field>

      <Field id={fieldId("status")} label={t("status")}>
        <select
          id={fieldId("status")}
          value={scene.status}
          onChange={(e) => patch({ status: e.target.value as SceneStatus })}
          className={INPUT_CLASS}
        >
          {STATUS_OPTIONS.map(({ value, labelKey }) => (
            <option key={value} value={value}>
              {t(labelKey)}
            </option>
          ))}
        </select>
      </Field>

      <BeatsEditor beats={scene.beats} onChange={(beats) => patch({ beats })} />
      <CharactersEditor
        characters={scene.present_characters}
        onChange={(present_characters) => patch({ present_characters })}
      />

      <div className="border-t border-border pt-2 space-y-1">
        <input
          aria-label={t("instruction")}
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          className={INPUT_CLASS}
        />
        <button
          type="button"
          onClick={handleRefine}
          disabled={refine.isPending}
          className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-primary/10 text-primary text-xs font-medium hover:bg-primary/20 disabled:opacity-50"
        >
          {refine.isPending ? (
            <Loader2 className="w-3 h-3 animate-spin" aria-hidden="true" />
          ) : (
            <Sparkles className="w-3 h-3" aria-hidden="true" />
          )}
          {t("refineWithAi")}
        </button>
        {(refine.isError || refine.data?.ai_unavailable) && (
          <p role="alert" className="text-xs text-destructive">
            {t("aiUnavailable")}
          </p>
        )}
      </div>
    </div>
  );
}
