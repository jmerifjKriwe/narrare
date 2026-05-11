"use client"

import { forwardRef } from "react"
import { cn } from "@/lib/utils"

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger"
  size?: "sm" | "md" | "lg"
  loading?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", loading, children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn("btn", `btn--${variant}`, `btn--${size}`, loading && "btn--loading", className)}
        {...props}
      >
        {loading ? (
          <span className="btn-spinner" aria-hidden="true" />
        ) : null}
        <span className={loading ? "btn-label--loading" : undefined}>{children}</span>

        <style jsx>{`
          .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            font-weight: 500;
            border-radius: var(--radius-md);
            border: 1px solid transparent;
            cursor: pointer;
            transition: background-color 0.15s, border-color 0.15s, opacity 0.15s;
            font-family: var(--font-sans);
            white-space: nowrap;
          }
          .btn:disabled { opacity: 0.5; cursor: not-allowed; }
          .btn--primary {
            background: var(--color-accent);
            color: white;
            border-color: var(--color-accent);
          }
          .btn--primary:hover:not(:disabled) { background: var(--color-accent-hover); }
          .btn--secondary {
            background: var(--color-surface);
            color: var(--color-text-primary);
            border-color: var(--color-border);
          }
          .btn--secondary:hover:not(:disabled) { background: var(--color-bg-secondary); }
          .btn--ghost {
            background: transparent;
            color: var(--color-text-secondary);
          }
          .btn--ghost:hover:not(:disabled) { background: var(--color-bg-tertiary); color: var(--color-text-primary); }
          .btn--danger {
            background: var(--color-error);
            color: white;
            border-color: var(--color-error);
          }
          .btn--sm { padding: 0.375rem 0.75rem; font-size: 0.8125rem; }
          .btn--md { padding: 0.5rem 1rem; font-size: 0.9375rem; }
          .btn--lg { padding: 0.75rem 1.5rem; font-size: 1rem; }
          .btn-spinner {
            width: 1em;
            height: 1em;
            border: 2px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 0.6s linear infinite;
          }
          @keyframes spin { to { transform: rotate(360deg); } }
          .btn-label--loading { opacity: 0.7; }
        `}</style>
      </button>
    )
  }
)
Button.displayName = "Button"
