# Phase C Task 1 Report — Route Shell Ownership Cleanup

## Status

Implementation and focused verification completed. Commit blocked by permissions during staging.

## Root cause

The observable drift was that `(studio)` route ownership rendered workspace chrome too broadly: dashboard and wizard/setup routes could sit under a layout that owned the persistent novel workspace sidebar. The underlying cause was shell ownership being centralized in the route-group layout instead of attached to the novel-scoped workspace route. The sustainable fix is to keep `(studio)` as an authentication boundary and move workspace chrome into `/novel/[id]/**` via `StudioWorkspaceShell`.

## Alternatives considered

1. Keep sidebar in `(studio)` and special-case wizard/dashboard routes. Rejected: this preserves shell ownership drift and adds route exceptions.
2. Move auth and workspace chrome into every page. Rejected: this duplicates auth/query/redirect logic and weakens shell contracts.
3. Chosen: extract `AuthGate`, make `(studio)` auth-only, and add a novel-scoped `StudioWorkspaceShell`. This addresses the root cause and matches the Phase C shell taxonomy.

## Files changed

- `packages/web/components/studio/shell/AuthGate.tsx`
- `packages/web/components/studio/shell/StudioWorkspaceShell.tsx`
- `packages/web/components/studio/shell/StudioWorkspaceShell.test.tsx`
- `packages/web/app/(studio)/novel/[id]/layout.tsx`
- `packages/web/components/studio/__tests__/ShellOwnership.test.tsx`
- `packages/web/app/(studio)/layout.tsx`
- `packages/web/app/(studio)/wizard/layout.tsx`
- `packages/web/components/studio/Sidebar.tsx`
- `packages/i18n/messages/de/studio.json`
- `packages/i18n/messages/en/studio.json`
- `packages/i18n/messages/fr/studio.json`

## RED evidence

Command:

```bash
pnpm --dir packages/web test components/studio/__tests__/ShellOwnership.test.tsx components/studio/shell/StudioWorkspaceShell.test.tsx
```

Expected failure observed before production implementation:

- `ShellOwnership.test.tsx` failed to resolve `@/app/(studio)/novel/[id]/layout` because the novel workspace layout did not exist.
- `StudioWorkspaceShell.test.tsx` failed to resolve `./StudioWorkspaceShell` because the workspace shell did not exist.
- Vitest summary: `Test Files 2 failed (2)`, `Tests no tests` due import-resolution failures for missing implementation files.

## GREEN verification

Command:

```bash
pnpm --dir packages/web test components/studio/__tests__/ShellOwnership.test.tsx components/studio/shell/StudioWorkspaceShell.test.tsx
```

Result: PASS — `2 passed`, `7 passed`.

Command:

```bash
pnpm --dir packages/web type-check
```

Result: PASS — `tsc --noEmit` completed with no TypeScript errors.

## Commit

- Message: `refactor(web): separate dashboard setup and workspace shells`
- Hash: none — blocked before commit
- Blocker: `BLOCKED: Need to run "git add packages/i18n/messages/de/studio.json packages/i18n/messages/en/studio.json packages/i18n/messages/fr/studio.json 'packages/web/app/(studio)/layout.tsx' 'packages/web/app/(studio)/wizard/layout.tsx' 'packages/web/app/(studio)/novel/[id]/layout.tsx' packages/web/components/studio/Sidebar.tsx packages/web/components/studio/__tests__/ShellOwnership.test.tsx packages/web/components/studio/shell/AuthGate.tsx packages/web/components/studio/shell/StudioWorkspaceShell.tsx packages/web/components/studio/shell/StudioWorkspaceShell.test.tsx" but permission denied. Please escalate.`

## Self-review

- Root cause addressed: shell ownership moved from broad route group chrome to auth-only boundary plus novel-scoped workspace shell.
- No workaround/special-case route bypass introduced.
- No new runtime dependency and no `middleware.ts` added.
- User-facing shell labels are i18n-backed in `de`, `en`, and `fr` locale files.
- Tailwind utility classes only; no inline styles.
- Components remain small and single-purpose: auth gate, workspace shell, route layout, sidebar props.
- Responsive shell behavior has regression tests for desktop sidebar, drawer open/close callback, and Escape close.
- TDD evidence captured: failing tests were run before production implementation, then focused tests and type-check passed.
