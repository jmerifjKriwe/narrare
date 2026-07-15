"use client";

/**
 * Renders the appropriate input control for a KB template field.
 *
 * Maps field_type to UI control:
 *   "str"  → text input
 *   "int"  → number input
 *   "bool" → toggle switch
 *   "list" → tag chip input
 *   *      → text input (fallback)
 */

import { useTranslations } from "next-intl";

import type { KBTemplateField } from "@/lib/api/kb";
import { KBFieldLabel } from "./KBFieldLabel";
import { KBTagInput } from "./KBTagInput";

interface KBTypeFieldProps {
  /** The template field definition. */
  field: KBTemplateField;
  /** Current value of the field. */
  value: unknown;
  /** Called with the new value when the field changes. */
  onChange: (name: string, value: unknown) => void;
  /** Translated label for the field. */
  label: string;
  /** Group name used to build i18n description keys. */
  groupName?: string;
  /** Error message if any. */
  error?: string;
}

/** Shared inline error message (extracted to keep KBTypeField under RULE-04). */
function FieldError({ id, error }: { id?: string; error?: string }) {
  if (!error) return null;
  return (
    <p id={id} className="text-xs text-destructive mt-1" role="alert">
      {error}
    </p>
  );
}

export function KBTypeField({ field, value, onChange, label, groupName, error }: KBTypeFieldProps) {
  const t = useTranslations("studio");
  const fieldId = `kb-field-${field.name}`;

  /**
   * Resolve description text from i18n (`kb.fieldDesc.{group}.{field}`).
   * Returns null when neither i18n key nor field.description exists.
   */
  const descriptionText = (() => {
    if (groupName) {
      const i18nKey = `kb.fieldDesc.${groupName}.${field.name}`;
      const i18nVal = t(i18nKey);
      if (i18nVal !== i18nKey) return i18nVal;
    }
    return field.description || null;
  })();

  /** Placeholder text — falls back to description then label. */
  const placeholder = descriptionText ?? label;

  function handleStrChange(e: React.ChangeEvent<HTMLInputElement>) {
    onChange(field.name, e.target.value);
  }

  function handleIntChange(e: React.ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value;
    onChange(field.name, raw === "" ? "" : Number(raw));
  }

  function handleBoolChange() {
    onChange(field.name, !value);
  }

  function handleListChange(newTags: string[]) {
    onChange(field.name, newTags);
  }

  // Common input styling
  const inputClass =
    "w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm " +
    "transition-colors duration-150 " +
    "hover:border-muted-foreground/30 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/20 " +
    "placeholder:text-muted-foreground/40 " +
    (error ? "border-destructive focus:border-destructive focus:ring-destructive/20" : "");

  const baseId = `field-${field.name}`;

  switch (field.field_type) {
    case "int":
      return (
        <div>
          <KBFieldLabel
            htmlFor={baseId}
            label={label}
            required={field.required}
            helpText={descriptionText}
          />
          <input
            id={baseId}
            type="number"
            value={value !== undefined && value !== null ? String(value) : ""}
            onChange={handleIntChange}
            placeholder={placeholder}
            className={inputClass}
            aria-invalid={!!error}
            aria-describedby={error ? `${baseId}-error` : undefined}
          />
          <FieldError id={`${baseId}-error`} error={error} />
        </div>
      );

    case "bool":
      return (
        <div>
          <div className="flex items-center justify-between">
            <KBFieldLabel
              htmlFor={fieldId}
              label={label}
              required={field.required}
              helpText={descriptionText}
              className="text-xs font-medium text-muted-foreground"
            />
            <button
              id={fieldId}
              type="button"
              role="switch"
              aria-checked={Boolean(value)}
              onClick={handleBoolChange}
              className={`
                relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full
                border-2 border-transparent transition-colors duration-200
                focus:outline-none focus:ring-2 focus:ring-primary/30 focus:ring-offset-1
                ${value ? "bg-primary" : "bg-muted-foreground/30"}
              `}
            >
              <span
                className={`
                  pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow
                  transform ring-0 transition-transform duration-200
                  ${value ? "translate-x-4" : "translate-x-0"}
                `}
              />
            </button>
          </div>
          <FieldError error={error} />
        </div>
      );

    case "list":
      return (
        <div>
          <KBFieldLabel
            as="span"
            label={label}
            required={field.required}
            helpText={descriptionText}
          />
          <KBTagInput
            value={Array.isArray(value) ? (value as string[]) : []}
            onChange={handleListChange}
            placeholder={placeholder}
          />
          <FieldError error={error} />
        </div>
      );

    // "str" and default
    default:
      return (
        <div>
          <KBFieldLabel
            htmlFor={baseId}
            label={label}
            required={field.required}
            helpText={descriptionText}
          />
          <input
            id={baseId}
            type="text"
            value={value !== undefined && value !== null ? String(value) : ""}
            onChange={handleStrChange}
            placeholder={placeholder}
            className={inputClass}
            aria-invalid={!!error}
            aria-describedby={error ? `${baseId}-error` : undefined}
          />
          <FieldError id={`${baseId}-error`} error={error} />
        </div>
      );
  }
}
