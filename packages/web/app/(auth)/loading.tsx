export default function AuthLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg-secondary)] p-4">
      <div className="w-full max-w-[400px] rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-8 shadow-[var(--shadow-md)]">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-2 h-7 w-28 animate-pulse rounded bg-[var(--color-bg-tertiary)]" />
          <div className="mx-auto h-4 w-24 animate-pulse rounded bg-[var(--color-bg-tertiary)]" />
        </div>
        <div className="space-y-4">
          <div className="h-10 animate-pulse rounded-lg bg-[var(--color-bg-tertiary)]" />
          <div className="h-10 animate-pulse rounded-lg bg-[var(--color-bg-tertiary)]" />
          <div className="h-10 animate-pulse rounded-lg bg-[var(--color-bg-tertiary)]" />
        </div>
      </div>
    </div>
  );
}
