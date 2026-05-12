export default function EditorLoading() {
  return (
    <div className="flex h-screen flex-col bg-[var(--color-bg-primary)]">
      {/* Toolbar */}
      <div className="h-[44px] shrink-0 border-b border-[var(--color-border)] bg-[var(--color-surface)]" />

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar — chapter list */}
        <div className="w-[240px] shrink-0 border-r border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <div className="mb-4 h-4 w-20 animate-pulse rounded bg-[var(--color-bg-tertiary)]" />
          <div className="mb-3 h-5 w-4/5 animate-pulse rounded bg-[var(--color-bg-tertiary)]" />
          <div className="mb-3 h-5 w-3/4 animate-pulse rounded bg-[var(--color-bg-tertiary)]" />
          <div className="mb-3 h-5 w-5/6 animate-pulse rounded bg-[var(--color-bg-tertiary)]" />
          <div className="mb-3 h-5 w-2/3 animate-pulse rounded bg-[var(--color-bg-tertiary)]" />
          <div className="mb-3 h-5 w-3/4 animate-pulse rounded bg-[var(--color-bg-tertiary)]" />
        </div>

        {/* Main content area */}
        <div className="flex-1 p-8">
          <div className="mx-auto max-w-[68ch]">
            <div className="mb-4 h-7 w-3/5 animate-pulse rounded bg-[var(--color-bg-tertiary)]" />
            <div className="mb-3 h-4 w-full animate-pulse rounded bg-[var(--color-bg-tertiary)]" />
            <div className="mb-3 h-4 w-11/12 animate-pulse rounded bg-[var(--color-bg-tertiary)]" />
            <div className="mb-3 h-4 w-4/5 animate-pulse rounded bg-[var(--color-bg-tertiary)]" />
          </div>
        </div>
      </div>
    </div>
  );
}
