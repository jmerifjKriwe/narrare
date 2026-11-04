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

const CONTROL_BASE =
  "rounded-[var(--radius)] border border-border bg-card px-2 text-body focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50";

/**
 * The control's class matrix — the input/select/textarea contract, pinned
 * beside `buttonClass`. `grows` swaps the fixed 28px height for a minimum:
 * a textarea grows with its rows, inputs and selects stay one line.
 */
export function controlClass(grows = false): string {
  return `${grows ? "min-h-7" : "h-7"} ${CONTROL_BASE}`;
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

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  const { id, describedBy, ariaInvalid } = useFieldControl();
  const {
    className,
    "aria-describedby": describedby,
    "aria-invalid": invalid,
    ...rest
  } = props;
  return (
    <select
      {...rest}
      id={id(props.id)}
      aria-describedby={describedBy(describedby)}
      aria-invalid={invalid || ariaInvalid}
      className={className ? `${controlClass()} ${className}` : controlClass()}
    />
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
        className ? `${controlClass(true)} ${className}` : controlClass(true)
      }
    />
  );
}
