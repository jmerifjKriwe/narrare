"use client"

import { forwardRef } from "react"
import { cn } from "@/lib/utils"

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  hint?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, hint, id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, "-")

    return (
      <div className="input-wrapper">
        {label && (
          <label htmlFor={inputId} className="input-label">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={cn("input", error && "input--error", className)}
          aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
          aria-invalid={!!error}
          {...props}
        />
        {hint && !error && (
          <p id={`${inputId}-hint`} className="input-hint">{hint}</p>
        )}
        {error && (
          <p id={`${inputId}-error`} className="input-error" role="alert">{error}</p>
        )}

        <style jsx>{`
          .input-wrapper { display: flex; flex-direction: column; gap: 0.375rem; }
          .input-label {
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--color-text-primary);
          }
          .input {
            width: 100%;
            padding: 0.5rem 0.75rem;
            border: 1px solid var(--color-border);
            border-radius: var(--radius-md);
            background: var(--color-surface);
            color: var(--color-text-primary);
            font-size: 0.9375rem;
            font-family: var(--font-sans);
            transition: border-color 0.15s;
            outline: none;
          }
          .input::placeholder { color: var(--color-text-placeholder); }
          .input:focus { border-color: var(--color-border-focus); }
          .input--error { border-color: var(--color-error); }
          .input-hint { font-size: 0.8125rem; color: var(--color-text-secondary); }
          .input-error { font-size: 0.8125rem; color: var(--color-error); }
        `}</style>
      </div>
    )
  }
)
Input.displayName = "Input"
