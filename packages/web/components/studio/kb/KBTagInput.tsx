"use client";

/**
 * Reusable tag/chip input component.
 *
 * Type a tag and press Enter or comma to add it as a chip.
 * Click the X on a chip to remove it.
 * Backspace in an empty input removes the last chip.
 */

import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

interface KBTagInputProps {
  /** Current list of tags. */
  value: string[];
  /** Called with the updated tag array on every change. */
  onChange: (tags: string[]) => void;
  /** Placeholder text for the input field. */
  placeholder?: string;
  /** Disable interactions. */
  disabled?: boolean;
}

export function KBTagInput({ value, onChange, placeholder, disabled }: KBTagInputProps) {
  const t = useTranslations("studio");
  const [inputValue, setInputValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  function addTag(raw: string) {
    const tag = raw.trim().replace(/,+$/, "").trim();
    if (!tag) return;
    if (value.includes(tag)) return;
    onChange([...value, tag]);
    setInputValue("");
  }

  function removeTag(index: number) {
    onChange(value.filter((_, i) => i !== index));
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag(inputValue);
    }
    if (e.key === "Backspace" && inputValue === "" && value.length > 0) {
      removeTag(value.length - 1);
    }
  }

  function handlePaste(e: React.ClipboardEvent<HTMLInputElement>) {
    const pasted = e.clipboardData.getData("text");
    if (pasted.includes(",")) {
      e.preventDefault();
      const parts = pasted
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const merged = [...value];
      for (const part of parts) {
        if (!merged.includes(part)) merged.push(part);
      }
      onChange(merged);
    }
  }

  function handleBlur() {
    if (inputValue.trim()) {
      addTag(inputValue);
    }
  }

  return (
    <div
      onClick={() => inputRef.current?.focus()}
      onKeyDown={() => {}}
      className={`
        flex flex-wrap items-center gap-1.5 px-3 py-2
        bg-input-background border border-border rounded-md
        text-sm min-h-[40px] cursor-text
        transition-colors duration-150
        ${disabled ? "opacity-50 cursor-not-allowed" : "hover:border-muted-foreground/30"}
      `}
      role="listbox"
      aria-label={placeholder ?? t("kb.tags")}
    >
      {value.map((tag, index) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full
            bg-primary/10 text-primary text-xs font-medium
            shadow-sm ring-1 ring-primary/10"
          role="option"
          aria-selected={true}
          tabIndex={-1}
        >
          {tag}
          {!disabled && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                removeTag(index);
              }}
              className="hover:bg-primary/20 rounded-full p-0.5 transition-colors
                focus:outline-none focus:ring-2 focus:ring-primary/30"
              aria-label={`Remove ${tag}`}
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </span>
      ))}
      <input
        ref={inputRef}
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        onBlur={handleBlur}
        disabled={disabled}
        {...(value.length === 0 ? { placeholder } : {})}
        className="flex-1 min-w-[80px] bg-transparent border-none outline-none
          text-sm text-foreground placeholder:text-muted-foreground/50"
        aria-label="Add tag"
      />
    </div>
  );
}
