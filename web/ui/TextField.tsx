import {
  FieldError,
  Input,
  Label,
  TextField as RacTextField,
  TextArea,
} from "react-aria-components";

/**
 * The shell's labeled text field. React-Aria wires the label to the input,
 * reports focus as data attributes and — through `isInvalid` — carries the
 * invalid state to the input's aria and paint; `validationMessage` rides a
 * real FieldError, associated by React-Aria, so the words reach a screen
 * reader with the field they name. The tokens do the painting. `multiline`
 * swaps the input for a textarea rather than growing a second component —
 * a blurb is the only multi-line need so far.
 */
export function TextField({
  label,
  value,
  onChange,
  multiline = false,
  isInvalid = false,
  validationMessage,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
  isInvalid?: boolean;
  validationMessage?: string;
}) {
  const field =
    "w-full rounded-md border border-border bg-card px-3 py-2 text-base font-normal data-focused:border-primary data-focused:outline-none data-focused:ring-2 data-focused:ring-focus data-invalid:border-danger";
  return (
    <RacTextField
      value={value}
      onChange={onChange}
      isInvalid={isInvalid}
      className="flex flex-col gap-1"
    >
      <Label className="text-sm font-medium">{label}</Label>
      {multiline ? (
        <TextArea rows={4} className={field} />
      ) : (
        <Input className={field} />
      )}
      {validationMessage !== undefined ? (
        <FieldError className="text-sm text-danger">{validationMessage}</FieldError>
      ) : null}
    </RacTextField>
  );
}
