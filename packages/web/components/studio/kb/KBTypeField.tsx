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

import type { KBTemplateField } from "@/lib/api/kb";
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
  /** Error message if any. */
  error?: string;
}

export function KBTypeField({ field, value, onChange, label, error }: KBTypeFieldProps) {
  const fieldId = `kb-field-${field.name}`;

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
          <label
            htmlFor={baseId}
            className="block text-xs font-medium text-muted-foreground mb-1.5"
          >
            {label}
            {field.required && <span className="text-destructive ml-0.5">*</span>}
          </label>
          <input
            id={baseId}
            type="number"
            value={value !== undefined && value !== null ? String(value) : ""}
            onChange={handleIntChange}
            placeholder={field.description || label}
            className={inputClass}
            aria-invalid={!!error}
            aria-describedby={error ? `${baseId}-error` : undefined}
          />
          {error && (
            <p id={`${baseId}-error`} className="text-xs text-destructive mt-1" role="alert">
              {error}
            </p>
          )}
        </div>
      );

    case "bool":
      return (
        <div>
          <div className="flex items-center justify-between">
            <label htmlFor={fieldId} className="text-xs font-medium text-muted-foreground">
              {label}
              {field.required && <span className="text-destructive ml-0.5">*</span>}
            </label>
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
          {field.description && (
            <p className="text-xs text-muted-foreground/60 mt-1">{field.description}</p>
          )}
          {error && (
            <p className="text-xs text-destructive mt-1" role="alert">
              {error}
            </p>
          )}
        </div>
      );

    case "list":
      return (
        <div>
          <span className="block text-xs font-medium text-muted-foreground mb-1.5">
            {label}
            {field.required && <span className="text-destructive ml-0.5">*</span>}
          </span>
          <KBTagInput
            value={Array.isArray(value) ? (value as string[]) : []}
            onChange={handleListChange}
            placeholder={field.description || label}
          />
          {error && (
            <p className="text-xs text-destructive mt-1" role="alert">
              {error}
            </p>
          )}
        </div>
      );

    // "str" and default
    default:
      return (
        <div>
          <label
            htmlFor={baseId}
            className="block text-xs font-medium text-muted-foreground mb-1.5"
          >
            {label}
            {field.required && <span className="text-destructive ml-0.5">*</span>}
          </label>
          <input
            id={baseId}
            type="text"
            value={value !== undefined && value !== null ? String(value) : ""}
            onChange={handleStrChange}
            placeholder={field.description || label}
            className={inputClass}
            aria-invalid={!!error}
            aria-describedby={error ? `${baseId}-error` : undefined}
          />
          {error && (
            <p id={`${baseId}-error`} className="text-xs text-destructive mt-1" role="alert">
              {error}
            </p>
          )}
        </div>
      );
  }
}
