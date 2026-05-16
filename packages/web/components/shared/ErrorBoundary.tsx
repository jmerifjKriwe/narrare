"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  componentDidCatch(error: Error, _errorInfo: ErrorInfo): void {
    this.setState({ hasError: true, error });
    this.props.onError?.(error);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="flex flex-col items-center justify-center gap-4 rounded-xl px-6 py-8 text-center bg-destructive/10">
          <p className="text-sm font-medium text-destructive">
            {this.state.error?.message || "Something went wrong"}
          </p>
          {/* eslint-disable i18next/no-literal-string */}
          <button
            type="button"
            onClick={() => this.setState({ hasError: false, error: null })}
            className="rounded-md px-4 py-2 text-sm font-medium transition-colors bg-primary text-primary-foreground"
          >
            Try again
          </button>
          {/* eslint-enable i18next/no-literal-string */}
        </div>
      );
    }

    return this.props.children;
  }
}
