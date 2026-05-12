"use client";

/* eslint-disable i18next/no-literal-string */
// Root error boundary must work without i18n — runs before providers are mounted.

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            minHeight: "100vh",
            fontFamily: "system-ui, sans-serif",
            padding: "2rem",
            textAlign: "center",
          }}
        >
          <h1 style={{ fontSize: "1.5rem", fontWeight: 600, marginBottom: "0.5rem" }}>
            Something went wrong
          </h1>
          <p style={{ color: "#6b6860", marginBottom: "1.5rem" }}>An unexpected error occurred.</p>
          <button
            type="button"
            onClick={() => reset()}
            style={{
              padding: "0.5rem 1.25rem",
              borderRadius: "0.375rem",
              border: "1px solid #e2e0db",
              background: "#ffffff",
              cursor: "pointer",
              fontSize: "0.875rem",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
