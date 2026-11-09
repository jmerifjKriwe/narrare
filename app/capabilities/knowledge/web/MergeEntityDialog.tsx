import { useState } from "react";

import { announce } from "@shell/lib/announce";
import type { Entity } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { useMergeEntities } from "@shell/lib/query";
import { Button } from "@shell/ui/Button";
import { ComboBox } from "@shell/ui/ComboBox";
import { Dialog } from "@shell/ui/Dialog";
import { Notice } from "@shell/ui/Notice";

/** Two entries for the same thing fold into one: the picker offers the
 *  novel's other entities, the target survives, the source is deleted. */
export function MergeEntityDialog({
  entity,
  others,
  novelId,
  onSelect,
}: {
  entity: Entity;
  others: Entity[];
  novelId: string;
  onSelect: (id: string | null) => void;
}) {
  const t = useTranslation();
  const merge = useMergeEntities(novelId);
  const [targetText, setTargetText] = useState("");
  const [targetId, setTargetId] = useState<string | null>(null);
  const [triedSave, setTriedSave] = useState(false);
  const [failed, setFailed] = useState(false);

  // The picked id must still be what the box says: typing a different name
  // after a pick is a new question, not a stale answer.
  const target = others.find((row) => row.id === targetId) ?? null;
  const targetInvalid = triedSave && (target === null || target.name !== targetText.trim());

  /** Merge into the still-matching picked target and select the survivor; expose failures. */
  async function mergeThem(close: () => void) {
    // One submit is one request, the save's rule again: a merge doubles a
    // deletion, so a second click must not race the first.
    if (merge.isPending) return;
    setTriedSave(true);
    setFailed(false);
    if (target === null || target.name !== targetText.trim()) return;
    try {
      const survivor = await merge.mutateAsync({ sourceId: entity.id, targetId: target.id });
      // The detail follows the surviving row: the source is deleted, and
      // the merge's answer is what remains to be seen.
      onSelect(survivor.id);
      announce(
        t("knowledge.entityMerged", { name: entity.name, target: survivor.name }),
      );
      close();
    } catch {
      setFailed(true);
    }
  }

  return (
    <Dialog title={t("knowledge.entityMergeTitle")} triggerLabel={t("knowledge.entityMerge")}>
      {(close) => (
        <div className="mt-4 flex flex-col gap-3">
          <p className="text-body">{t("knowledge.entityMergeText", { name: entity.name })}</p>
          <ComboBox
            label={t("knowledge.entityMergeTargetLabel")}
            value={targetText}
            onChange={setTargetText}
            onPick={(id) => {
              setTargetId(id);
              const picked = others.find((row) => row.id === id);
              if (picked) setTargetText(picked.name);
            }}
            items={others
              .filter((row) => row.name.toLowerCase().includes(targetText.trim().toLowerCase()))
              .map((row) => ({ id: row.id, text: row.name }))}
          />
          {targetInvalid ? (
            <Notice tone="danger">{t("knowledge.entityMergeTargetRequired")}</Notice>
          ) : null}
          {failed ? (
            <Notice tone="danger" live="alert">
              {t("knowledge.entityFailed")}
            </Notice>
          ) : null}
          <div className="flex gap-2">
            <Button
              variant="primary"
              onClick={() => void mergeThem(close)}
              disabled={merge.isPending}
            >
              {t("knowledge.entityMergeConfirm")}
            </Button>
            <Button onClick={close}>{t("knowledge.entityCancel")}</Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
