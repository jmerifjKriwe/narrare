import {
  createContext,
  useContext,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type Ref,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

import { Icon } from "./icons";

/**
 * The labelled form field: `Field` owns the label, the hint and the error;
 * `Input`, `Select` and `Textarea` are the native controls that live inside
 * it. The wiring is the accessibility contract — the label points at the
 * control's id, the control's `aria-describedby` names the hint and the
 * error, the error rides `role="alert"` so it is announced when it
 * appears, and an errored control also wears `aria-invalid`. One focus
 * treatment everywhere: the ring, never `focus:outline-none` with a border
 * change.
 */

/**
 * The control's geometry — the drafted shells (spec §6.5): the 8 px control
 * radius, the button ladder's amber focus ring with its 1 px gap, and the
 * height the size axis names. One definition here, so the input, the
 * select, the textarea and the file input cannot drift apart.
 */
const CONTROL_BASE =
  "rounded-[var(--radius-control)] border border-border bg-card px-2 text-body focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent disabled:opacity-50";

/**
 * The two heights a control wears: the drafted default (36 px, the button
 * ladder's middle rung) and the compact one (32 px) for the dense rows.
 */
export type ControlSize = "md" | "compact";

/** The height each size pins, and the floor the growing control starts from. */
const CONTROL_HEIGHTS: Record<ControlSize, string> = {
  md: "h-9",
  compact: "h-8",
};
const CONTROL_FLOORS: Record<ControlSize, string> = {
  md: "min-h-9",
  compact: "min-h-8",
};

/**
 * The control's class matrix — the input/select/textarea contract, pinned
 * beside `buttonClass`. `size` picks the height; `grows` swaps that fixed
 * height for a minimum: a textarea grows with its rows, inputs and selects
 * stay one line.
 */
export function controlClass({
  grows = false,
  size = "md",
}: { grows?: boolean; size?: ControlSize } = {}): string {
  const height = grows ? CONTROL_FLOORS[size] : CONTROL_HEIGHTS[size];
  return `${height} ${CONTROL_BASE}`;
}

const FILE_CONTROL_CLASSES = `${controlClass()} file:mr-3 file:rounded-[var(--radius)] file:border-0 file:bg-transparent file:text-label file:font-medium`;

/**
 * The file input: the control contract plus the native `::file-selector-
 * button` painted into the system — the label size, the token radius, no
 * border of its own. The one shared voice for every upload control (the
 * interchange dialog's, the knowledge page's), so the legacy `text-sm`/
 * bare-radius paint cannot come back (#529/#530). Field wiring rides
 * through like `Input`'s.
 */
export function FileInput(
  props: InputHTMLAttributes<HTMLInputElement> & {
    ref?: Ref<HTMLInputElement>;
  },
) {
  const { id, describedBy, ariaInvalid } = useFieldControl();
  const {
    className,
    "aria-describedby": describedby,
    "aria-invalid": invalid,
    ...rest
  } = props;
  return (
    <input
      {...rest}
      type="file"
      id={id(props.id)}
      aria-describedby={describedBy(describedby)}
      aria-invalid={invalid || ariaInvalid}
      className={
        className
          ? `${FILE_CONTROL_CLASSES} ${className}`
          : FILE_CONTROL_CLASSES
      }
    />
  );
}

/** A field stacks label, control and messages at the scale's label gap. */
const FIELD_CLASSES = "flex flex-col gap-1";

type FieldContextValue = {
  id: string;
  hintId: string | undefined;
  errorId: string | undefined;
  ariaInvalid: true | undefined;
};

const FieldContext = createContext<FieldContextValue | null>(null);

/**
 * The invalid-state attribute a field's control carries: `aria-invalid`
 * when an error is shown, nothing otherwise — the pair screen readers
 * expect alongside the announced error. An empty string is no error: it
 * would render an empty alert and a falsely invalid field.
 */
export function fieldAria(
  error: string | undefined,
): { "aria-invalid"?: true } {
  return error ? { "aria-invalid": true } : {};
}

export function Field({
  label,
  hint,
  error,
  id,
  className,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  /** The control's id; a generated one when omitted. */
  id?: string;
  className?: string;
  children: ReactNode;
}) {
  const generated = useId();
  const fieldId = id ?? generated;
  const hintId = hint ? `${fieldId}-hint` : undefined;
  const errorId = error ? `${fieldId}-error` : undefined;
  const { "aria-invalid": ariaInvalid } = fieldAria(error);
  return (
    <FieldContext.Provider
      value={{ id: fieldId, hintId, errorId, ariaInvalid }}
    >
      <div
        className={
          className ? `${FIELD_CLASSES} ${className}` : FIELD_CLASSES
        }
      >
        <label htmlFor={fieldId} className="block text-label font-medium">
          {label}
        </label>
        {children}
        {hint ? (
          <p id={hintId} className="text-label text-muted">
            {hint}
          </p>
        ) : null}
        {error ? (
          <p id={errorId} role="alert" className="text-label text-danger">
            {error}
          </p>
        ) : null}
      </div>
    </FieldContext.Provider>
  );
}

/**
 * Inside a `Field`, a control inherits its id (so the label's `htmlFor`
 * lands) and describes itself with whichever hint and error exist — a
 * control that drops either stops describing itself. A caller's own
 * `aria-describedby` survives, joined in front. The caller's explicit
 * `aria-invalid` joins the field's with `||`, never `??`: an explicit
 * false must not mask a shown error.
 */
function useFieldControl() {
  const field = useContext(FieldContext);
  return {
    // The field's id wins: a caller-supplied control id would leave the
    // label's `htmlFor` pointing at nothing.
    id: (propsId: string | undefined) => field?.id ?? propsId,
    describedBy: (own: string | undefined) =>
      [own, field?.hintId, field?.errorId].filter(Boolean).join(" ") ||
      undefined,
    ariaInvalid: field?.ariaInvalid,
  };
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  const { id, describedBy, ariaInvalid } = useFieldControl();
  const {
    className,
    "aria-describedby": describedby,
    "aria-invalid": invalid,
    ...rest
  } = props;
  return (
    <input
      {...rest}
      id={id(props.id)}
      aria-describedby={describedBy(describedby)}
      aria-invalid={invalid || ariaInvalid}
      className={className ? `${controlClass()} ${className}` : controlClass()}
    />
  );
}

/**
 * The select's own string: the control contract plus the three
 * companions of the custom chevron — the native arrow off, the room the
 * chevron needs on the right, the width the shell fills — and the `peer`
 * that lets the caret dim with a disabled control.
 */
const SELECT_CLASSES = `${controlClass()} peer w-full appearance-none pr-8`;

/**
 * The caret's place in the shell: right of the value, centred, and in the
 * muted ink — a graphic, not text. It never takes the pointer, so the
 * native control keeps the whole click.
 */
const CHEVRON_CLASSES =
  "pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-muted peer-disabled:opacity-50";

/**
 * The select's shell: the native control, its own arrow off, and the app's
 * chevron beside it. The element stays native on purpose — the popup is the
 * browser's own and follows the theme's `color-scheme`; what the app owns
 * is the shell around it: the height, the radius, the ring and the caret.
 * The caret is the icon set's glyph, drawn in the control's ink, so it
 * follows the theme and never names itself.
 */
export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  const { id, describedBy, ariaInvalid } = useFieldControl();
  const {
    className,
    children,
    "aria-describedby": describedby,
    "aria-invalid": invalid,
    ...rest
  } = props;
  return (
    <span className="relative inline-flex items-center">
      <select
        {...rest}
        id={id(props.id)}
        aria-describedby={describedBy(describedby)}
        aria-invalid={invalid || ariaInvalid}
        className={className ? `${SELECT_CLASSES} ${className}` : SELECT_CLASSES}
      >
        {children}
      </select>
      <span className={CHEVRON_CLASSES}>
        <Icon name="selectChevron" />
      </span>
    </span>
  );
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const { id, describedBy, ariaInvalid } = useFieldControl();
  const {
    className,
    "aria-describedby": describedby,
    "aria-invalid": invalid,
    ...rest
  } = props;
  return (
    <textarea
      {...rest}
      id={id(props.id)}
      aria-describedby={describedBy(describedby)}
      aria-invalid={invalid || ariaInvalid}
      className={
        className
          ? `${controlClass({ grows: true })} ${className}`
          : controlClass({ grows: true })
      }
    />
  );
}
