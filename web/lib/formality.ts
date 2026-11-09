/**
 * The register the interface addresses the reader in.
 *
 * German and French distinguish a familiar register (du, tu) from a neutral
 * one (Sie, vous); English has no such choice. The base catalogs keep the
 * familiar register — the product's default — and a sparse overlay carries
 * only the strings whose formal wording differs. The choice is local to the
 * browser: it never leaves this device and never reaches a prompt.
 */

export type Formality = "informal" | "formal";

const STORAGE_KEY = "narrare.formality";

function isFormality(value: string | null): value is Formality {
  return value === "informal" || value === "formal";
}

let active: Formality = "informal";
const listeners = new Set<() => void>();

/** The register `t()` renders in. */
export function activeFormality(): Formality {
  return active;
}

export function subscribeFormality(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function announce(next: Formality): void {
  if (next === active) return;
  active = next;
  for (const listener of listeners) listener();
}

/** A choice made in the UI, applied immediately and remembered locally. */
export function applyFormality(next: Formality): void {
  announce(next);
  if (typeof localStorage !== "undefined") localStorage.setItem(STORAGE_KEY, next);
}

/** The stored choice, read once at boot; an unknown value keeps the default. */
export function adoptStoredFormality(): void {
  if (typeof localStorage === "undefined") return;
  const stored = localStorage.getItem(STORAGE_KEY);
  if (isFormality(stored)) announce(stored);
}
