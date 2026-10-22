import { Input, Label, TextField as RacTextField, TextArea } from "react-aria-components";

/**
 * The shell's labeled text field. React-Aria wires the label to the input and
 * reports focus as data attributes; the tokens do the painting. `multiline`
 * swaps the input for a textarea rather than growing a second component — a
 * blurb is the only multi-line need so far.
 */
export function TextField({
  label,
  value,
  onChange,
  multiline = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
}) {
  const field =
    "w-full rounded-md border border-border bg-card px-3 py-2 text-base font-normal data-focused:border-primary data-focused:outline-none data-focused:ring-2 data-focused:ring-focus";
  return (
    <RacTextField value={value} onChange={onChange} className="flex flex-col gap-1">
      <Label className="text-sm font-medium">{label}</Label>
      {multiline ? (
        <TextArea rows={4} className={field} />
      ) : (
        <Input className={field} />
      )}
    </RacTextField>
  );
}
