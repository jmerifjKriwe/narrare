export default function EditorLoading() {
  return (
    <div className="flex h-full flex-col bg-background overflow-hidden">
      {/* Toolbar skeleton */}
      <div className="h-11 shrink-0 border-b border-border bg-muted" />

      <div className="flex-1 overflow-hidden">
        {/* Main content area skeleton — sidebar is handled by novel/[id]/layout.tsx */}
        <div className="flex justify-center py-6 px-4">
          <div className="w-full max-w-[780px] min-h-[calc(100vh-160px)] bg-card rounded-sm border border-border/50 p-8">
            <div className="mb-4 h-7 w-3/5 animate-pulse rounded bg-muted" />
            <div className="mb-3 h-4 w-full animate-pulse rounded bg-muted" />
            <div className="mb-3 h-4 w-11/12 animate-pulse rounded bg-muted" />
            <div className="mb-3 h-4 w-4/5 animate-pulse rounded bg-muted" />
          </div>
        </div>
      </div>

      {/* Status bar skeleton */}
      <div className="h-8 shrink-0 border-t border-border bg-muted" />
    </div>
  );
}
