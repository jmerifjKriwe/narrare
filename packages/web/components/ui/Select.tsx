"use client"

import { forwardRef } from "react"

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  options: { value: string; label: string }[]
  placeholder?: string
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, options, placeholder, id, ...props }, ref) => {
    const selectId = id || label?.toLowerCase().replace(/\s+/g, "-")

    return (
      <div className="select-wrapper">
        {label && <label htmlFor={selectId} className="select-label">{label}</label>}
        <select ref={ref} id={selectId} className={`select${error ? " select--error" : ""}`} {...props}>
          {placeholder && <option value="">{placeholder}</option>}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        {error && <p className="select-error" role="alert">{error}</p>}

        <style jsx>{`
          .select-wrapper { display: flex; flex-direction: column; gap: 0.375rem; }
          .select-label { font-size: 0.875rem; font-weight: 500; color: var(--color-text-primary); }
          .select {
            width: 100%;
            padding: 0.5rem 0.75rem;
            border: 1px solid var(--color-border);
            border-radius: var(--radius-md);
            background: var(--color-surface);
            color: var(--color-text-primary);
            font-size: 0.9375rem;
            font-family: var(--font-sans);
            cursor: pointer;
            outline: none;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%236b6860' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 0.75rem center;
            padding-right: 2.5rem;
          }
          .select:focus { border-color: var(--color-border-focus); }
          .select--error { border-color: var(--color-error); }
          .select-error { font-size: 0.8125rem; color: var(--color-error); }
        `}</style>
      </div>
    )
  }
)
Select.displayName = "Select"
