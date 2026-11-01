import {
  createContext,
  useContext,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

/**
 * The labelled form field: `Field` owns the label, the hint and the error;
 * `Input`, `Select` and `Textarea` are the native controls that live inside
 * it. The wiring is the accessibility contract — the label points at the
 * control's id, the control's `aria-describedby` names the hint and the
 * error, and the error rides `role="alert"` so it is announced when it
 * appears. One focus treatment everywhere: the ring, never
 * `focus:outline-none` with a border change.
 */

const CONTROL_CLASSES =
  "h-7 rounded-[var(--radius)] border border-border bg-card px-2 text-body focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

type FieldContextValue = {
  id: string;
  hintId: string | undefined;
  errorId: string | undefined;
};

const FieldContext = createContext<FieldContextValue | null>(null);

export function Field({
  label,
  hint,
  error,
  id,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  /** The control's id; a generated one when omitted. */
  id?: string;
  children: ReactNode;
}) {
  const generated = useId();
  const fieldId = id ?? generated;
  const hintId = hint !== undefined ? `${fieldId}-hint` : undefined;
  const errorId = error !== undefined ? `${fieldId}-error` : undefined;
  return (
    <FieldContext.Provider value={{ id: fieldId, hintId, errorId }}>
      <label htmlFor={fieldId} className="block text-label font-medium">
        {label}
      </label>
      {children}
      {hint !== undefined ? (
        <p id={hintId} className="text-label text-muted">
          {hint}
        </p>
      ) : null}
      {error !== undefined ? (
        <p id={errorId} role="alert" className="text-label text-danger">
          {error}
        </p>
      ) : null}
    </FieldContext.Provider>
  );
}

/**
 * Inside a `Field`, a control inherits its id (so the label's `htmlFor`
 * lands) and describes itself with whichever hint and error exist — a
 * control that drops either stops describing itself. A caller's own
 * `aria-describedby` survives, joined in front.
 */
function useFieldControl() {
  const field = useContext(FieldContext);
  return {
    id: (propsId: string | undefined) => propsId ?? field?.id,
    describedBy: (own: string | undefined) =>
      [own, field?.hintId, field?.errorId].filter(Boolean).join(" ") ||
      undefined,
  };
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  const { id, describedBy } = useFieldControl();
  const { className, "aria-describedby": describedby, ...rest } = props;
  return (
    <input
      {...rest}
      id={id(props.id)}
      aria-describedby={describedBy(describedby)}
      className={className ? `${CONTROL_CLASSES} ${className}` : CONTROL_CLASSES}
    />
  );
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  const { id, describedBy } = useFieldControl();
  const { className, "aria-describedby": describedby, ...rest } = props;
  return (
    <select
      {...rest}
      id={id(props.id)}
      aria-describedby={describedBy(describedby)}
      className={className ? `${CONTROL_CLASSES} ${className}` : CONTROL_CLASSES}
    />
  );
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const { id, describedBy } = useFieldControl();
  const { className, "aria-describedby": describedby, ...rest } = props;
  return (
    <textarea
      {...rest}
      id={id(props.id)}
      aria-describedby={describedBy(describedby)}
      className={className ? `${CONTROL_CLASSES} ${className}` : CONTROL_CLASSES}
    />
  );
}
