"use client";

/**
 * SeriesField — label + control wrapper for the Series settings form
 * (Spec 1, Slice 4, Task 4.7).
 *
 * Extracted from SeriesMetadataForm (RULE-04). A plain wrapper (not a
 * `<label>`) so each control's association is provided via its own `aria-label`
 * (matches the GeneralTab pattern — Biome's label-association rule can't verify
 * an implicit association through dynamic children).
 */
interface SeriesFieldProps {
  readonly label: string;
  readonly children: React.ReactNode;
}

export function SeriesField({ label, children }: SeriesFieldProps) {
  return (
    <div>
      <span className="mb-1 block text-sm font-medium text-foreground">{label}</span>
      {children}
    </div>
  );
}
