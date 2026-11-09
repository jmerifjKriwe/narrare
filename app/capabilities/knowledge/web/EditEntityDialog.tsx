import { useState } from "react";

import { announce } from "@shell/lib/announce";
import type { Entity } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { useUpdateEntity, type EntityChanges } from "@shell/lib/query";
import { Button } from "@shell/ui/Button";
import { ComboBox } from "@shell/ui/ComboBox";
import { Dialog } from "@shell/ui/Dialog";
import { Field, Input } from "@shell/ui/field";
import { Icon } from "@shell/ui/icons";
import { MarkdownEditor } from "@shell/ui/markdown-editor";
import { Notice } from "@shell/ui/Notice";

import { EntityRelationsSection } from "./EntityRelationsSection";
import { TYPE_KEYS, entityTypeLabel } from "./entityTypes";

/** The chips input on top of the shell's text field: Enter or comma files
 *  the text as a chip, and so does leaving the field — the Save click is
 *  such a leaving, so typed work is filed before the save reads the chips
 *  instead of lost in the box. ✕ removes one, and a case twin is turned
 *  away — the service dedupes too, this is the field's own courtesy. */
function ChipsField({
  label,
  values,
  onChange,
}: {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
}) {
  const t = useTranslation();
  const [text, setText] = useState("");

  function fileText() {
    const value = text.trim().replace(/,+$/, "");
    if (value === "") return;
    setText("");
    if (values.some((existing) => existing.toLowerCase() === value.toLowerCase())) return;
    onChange([...values, value]);
  }

  return (
    <div
      className="flex flex-col gap-1"
      onBlur={fileText}
      onKeyDown={(event) => {
        // The wrapper's keydown serves the text field only: a remove
        // button's Enter is a button press, so any other target is none
        // of this handler's business — swallowing it would kill the
        // chip's keyboard removal.
        if (!(event.target instanceof HTMLInputElement)) return;
        if (event.key === "Enter" || event.key === ",") {
          // Enter must not submit what sits around the field, and the
          // comma must not stay in it: both file the chip instead.
          event.preventDefault();
          fileText();
        }
      }}
    >
      {/* The row is reserved even when empty: a chips field that grows on
          its first commit moves everything below it — the save button
          included — in the same task as the commit's blur, and the click
          that caused the blur lands where the button was. The reserved
          row keeps the commit from moving what the pointer is aiming at
          (the upload-preservation class: a typed value must survive the
          interaction that files it). */}
      <ul className="flex min-h-6 flex-wrap gap-1">
        {values.map((value) => (
          <li
            key={value}
            className="flex items-center gap-1 rounded-full bg-panel px-2 py-0.5 text-label"
          >
            <span>{value}</span>
            <Button
              variant="icon"
              size="sm"
              icon={<Icon name="cross" />}
              label={t("knowledge.chipRemove", { value })}
              onClick={() => onChange(values.filter((existing) => existing !== value))}
            />
          </li>
        ))}
      </ul>
      <Field label={label}>
        <Input value={text} onChange={(event) => setText(event.target.value)} />
      </Field>
    </div>
  );
}

/** Order-sensitive list equality: a label field reaches the PATCH body
 *  only when the chips truly differ from what the row holds. */
function sameList(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

/** Every field of the row in one dialog (D9): name, type, aliases, tags,
 *  the Markdown body as plain source, and the relations with their add
 *  row. The container is no form — the relations section owns real forms
 *  of its own, and a nested form is no form at all. */
export function EditEntityDialog({
  entity,
  rows,
  novelId,
}: {
  entity: Entity;
  rows: Entity[];
  novelId: string;
}) {
  const t = useTranslation();
  const update = useUpdateEntity(novelId);
  const [name, setName] = useState(entity.name);
  const [typeText, setTypeText] = useState(entityTypeLabel(t, entity.type));
  const [aliases, setAliases] = useState<string[]>(entity.aliases);
  const [tags, setTags] = useState<string[]>(entity.tags);
  const [content, setContent] = useState(entity.content);
  // The refusals are derived, not stored: once a save was tried, the words
  // stand exactly as long as the field does not answer them.
  const [triedSave, setTriedSave] = useState(false);
  const [failed, setFailed] = useState(false);
  // A relation row editor holds typed work the entity save knows nothing
  // about — saving and closing now would silently discard it, so the save
  // button stands down while one is open.
  const [rowEditorOpen, setRowEditorOpen] = useState(false);
  const [addFormDirty, setAddFormDirty] = useState(false);

  const typeItems = (Object.keys(TYPE_KEYS) as (keyof typeof TYPE_KEYS)[]).map((type) => ({
    id: type,
    text: t(TYPE_KEYS[type]),
  }));
  const nameInvalid = triedSave && name.trim() === "";
  // The box is the source of truth: its text resolves back to a type on
  // save, the way the search box's text is what the list filters by.
  const resolvedType = typeItems.find((item) => item.text === typeText.trim())?.id ?? null;
  const typeInvalid = triedSave && resolvedType === null;

  /** Save changed fields, clearing a blank body; keep the dialog open on refusal. */
  async function save(close: () => void) {
    // One submit is one request: a click the pending save already owns is
    // no second ask.
    if (update.isPending) return;
    setTriedSave(true);
    setFailed(false);
    const trimmedName = name.trim();
    if (trimmedName === "" || resolvedType === null) return;
    const nextContent = content.trim() === "" ? "" : content;
    const changes: EntityChanges = {};
    if (trimmedName !== entity.name) changes.name = trimmedName;
    if (resolvedType !== entity.type) changes.type = resolvedType;
    if (!sameList(aliases, entity.aliases)) changes.aliases = aliases;
    if (!sameList(tags, entity.tags)) changes.tags = tags;
    if (nextContent !== entity.content) changes.content = nextContent;
    try {
      await update.mutateAsync({ entityId: entity.id, changes });
    } catch {
      // The dialog stays open: the typed values are the user's work, and
      // the failure is this save's own — named inside the dialog, where
      // the retry is one press away.
      setFailed(true);
      return;
    }
    announce(t("knowledge.entitySaved", { name: trimmedName }));
    close();
  }

  return (
    <Dialog title={t("knowledge.entityEditTitle")} triggerLabel={t("knowledge.entityEdit")}>
      {(close) => (
        <div className="mt-4 flex flex-col gap-3">
          <Field
            label={t("knowledge.entityNameLabel")}
            error={nameInvalid ? t("knowledge.entityNameRequired") : undefined}
          >
            <Input value={name} onChange={(event) => setName(event.target.value)} />
          </Field>
          <ComboBox
            label={t("knowledge.entityTypeLabel")}
            value={typeText}
            onChange={setTypeText}
            onPick={(id) => {
              const picked = typeItems.find((item) => item.id === id);
              if (picked) setTypeText(picked.text);
            }}
            items={typeItems.filter((item) =>
              item.text.toLowerCase().includes(typeText.trim().toLowerCase()),
            )}
          />
          {typeInvalid ? (
            <Notice tone="danger">{t("knowledge.entityTypeRequired")}</Notice>
          ) : null}
          <ChipsField
            label={t("knowledge.entityAliasesLabel")}
            values={aliases}
            onChange={setAliases}
          />
          <ChipsField label={t("knowledge.entityTagsLabel")} values={tags} onChange={setTags} />
          {/* F-26: the body is prose, edited as rich text and stored as
              Markdown — the same shared editor the chapters use. A blank
              editor still saves as a cleared body. */}
          <MarkdownEditor
            label={t("knowledge.entityBodyLabel")}
            value={content}
            onChange={setContent}
          />
          <EntityRelationsSection
            entity={entity}
            rows={rows}
            onRowEditorChange={setRowEditorOpen}
            onAddDirtyChange={setAddFormDirty}
          />
          {failed ? (
            <Notice tone="danger" live="alert">
              {t("knowledge.entityFailed")}
            </Notice>
          ) : null}
          <div className="flex gap-2">
            <Button
              variant="primary"
              onClick={() => void save(close)}
              disabled={rowEditorOpen || addFormDirty || update.isPending}
            >
              {t("knowledge.entitySave")}
            </Button>
            <Button onClick={close}>{t("knowledge.entityCancel")}</Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
