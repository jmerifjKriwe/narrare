import { useState } from "react";

import { announce } from "@shell/lib/announce";
import type { Entity } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { useDeleteEntity } from "@shell/lib/query";
import { Button } from "@shell/ui/Button";
import { Dialog } from "@shell/ui/Dialog";
import { Notice } from "@shell/ui/Notice";

/** The confirm the delete owes its blast radius: the dialog names the row
 *  it will take before it takes it. */
export function DeleteEntityDialog({
  entity,
  novelId,
  onSelect,
}: {
  entity: Entity;
  novelId: string;
  onSelect: (id: string | null) => void;
}) {
  const t = useTranslation();
  const remove = useDeleteEntity(novelId);
  const [failed, setFailed] = useState(false);

  /** Delete and clear the selection on success; keep the dialog open on failure. */
  async function destroy(close: () => void) {
    // One confirm is one request: a second press of the open dialog's
    // button waits for the first to settle.
    if (remove.isPending) return;
    setFailed(false);
    try {
      await remove.mutateAsync(entity.id);
    } catch {
      setFailed(true);
      return;
    }
    // The row is gone: the selection must not point at what no longer
    // exists, and the detail unmounts with the answer.
    onSelect(null);
    announce(t("knowledge.entityDeleted", { name: entity.name }));
    close();
  }

  return (
    <Dialog title={t("knowledge.entityDeleteTitle")} triggerLabel={t("knowledge.entityDelete")}>
      {(close) => (
        <div className="mt-4 flex flex-col gap-3">
          <p className="text-body">{t("knowledge.entityDeleteText", { name: entity.name })}</p>
          {failed ? (
            <Notice tone="danger" live="alert">
              {t("knowledge.entityFailed")}
            </Notice>
          ) : null}
          <div className="flex gap-2">
            {/* The destructive confirm stays a quiet button on purpose:
                the dialog's text carries the warning; the filled
                `--primary` is for the one advancing action, never for the
                button that destroys (the P12 guard's precedent). */}
            <Button onClick={() => void destroy(close)} disabled={remove.isPending}>
              {t("knowledge.entityDeleteConfirm")}
            </Button>
            <Button onClick={close}>{t("knowledge.entityCancel")}</Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
