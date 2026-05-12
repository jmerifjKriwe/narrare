export default function DashboardLoading() {
  return (
    <div className="mx-auto max-w-[900px] p-8">
      {/* Header row */}
      <div className="mb-8 flex items-center justify-between">
        <div className="h-8 w-48 animate-pulse rounded bg-[var(--color-bg-tertiary)]" />
        <div className="h-10 w-32 animate-pulse rounded-lg bg-[var(--color-bg-tertiary)]" />
      </div>

      {/* Novel card grid */}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
        <div className="h-32 animate-pulse rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]" />
        <div className="h-32 animate-pulse rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]" />
        <div className="h-32 animate-pulse rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]" />
      </div>
    </div>
  );
}
