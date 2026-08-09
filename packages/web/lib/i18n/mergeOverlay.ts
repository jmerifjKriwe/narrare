/**
 * Formality overlay deep-merge helper (Feature Spec I-Copy-001).
 *
 * Resolves the user-selected UI formality register (du/Sie, tutoyer/vouvoyer)
 * ONE LAYER BEFORE next-intl: the message loader (`request.ts`) merges a sparse
 * "formal" overlay over the base (informal-default) messages, so `next-intl`
 * and every useTranslations / t(...) call site stay 100 % unchanged.
 *
 * Deep-merge is MANDATORY (verified, not assumed): base namespaces contain
 * nested objects — e.g. `de/settings.json` → `themes: { light, dark, system }`.
 * A shallow merge would drop a sibling sub-tree when a single leaf is
 * overridden. This helper recurses into plain objects and replaces only the
 * targeted leaves; sibling leaves are preserved.
 *
 * RULE-02 boundary: this is UI-copy-only. It never touches `core/prompts/`.
 * RULE-06: this module does ONE thing — deep-merge two message objects.
 */

/** The user-selectable UI formality register. Default is `"informal"`. */
export type Formality = "informal" | "formal";

/** A next-intl message namespace tree (leaves are translation strings). */
type Messages = Record<string, unknown>;

/**
 * `true` for a plain object that should be recursed into (not an array or
 * class instance). Arrays are treated as leaf values (replaced wholesale) —
 * next-intl message JSON in this project contains no arrays.
 */
function isPlainObject(value: unknown): value is Messages {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    Object.getPrototypeOf(value) === Object.prototype
  );
}

/**
 * Recursively deep-merge `overlay` over `base`. Overlay leaf values win;
 * nested sibling leaves are preserved. Neither input is mutated — a NEW merged
 * object is returned (the loader caches imported modules, so mutating `base`
 * would corrupt the shared base catalog across requests).
 */
export function mergeOverlay(base: Messages, overlay: Messages): Messages {
  const out: Messages = { ...base };
  for (const [key, overlayValue] of Object.entries(overlay)) {
    const baseValue = out[key];
    out[key] =
      isPlainObject(baseValue) && isPlainObject(overlayValue)
        ? mergeOverlay(baseValue, overlayValue)
        : overlayValue;
  }
  return out;
}
