# Q-008 — Auth Store wird nach Page Reload nicht rehydriert

> **Status:** 🟡 Open
> **Blocks:** Alle Komponenten die `user.id` brauchen (WebSocket, personalisierte UI)
> **Raised:** 2026-05-18

---

## Problem

Nach einem Page Reload (F5) ist der Auth-Store leer: `user: null`, `isAuthenticated: false`. Obwohl ein gültiges httpOnly Refresh-Cookie existiert, wird die User-Session nicht wiederhergestellt.

### Root Cause

- `authStore.loadUser()` existiert und macht das Richtige (restoreSession → authApi.me → Store setzen)
- `loadUser()` wird **nie beim App-Start aufgerufen** — es gibt keinen AuthProvider, keinen useEffect im Root-Layout, keinen App-Initializer
- Der Access Token wird In-Memory gespeichert (`let _accessToken: string | null = null` in `client.ts`) — nach Reload weg
- Das httpOnly Refresh-Cookie überlebt den Reload, aber niemand nutzt es

### Aktueller Workaround (Session 2026-05-18)

`SessionPanel.tsx` ruft `loadUser()` selbst auf wenn `user` null ist:

```typescript
const loadUser = useAuthStore((s) => s.loadUser);

useEffect(() => {
  if (!currentUser && !isLoading) {
    loadUser();
  }
}, [currentUser, isLoading, loadUser]);
```

**Das ist ein Workaround, kein Fix.** SessionPanel sollte nicht für die Auth-Hydration verantwortlich sein. Jede Komponente die `user.id` braucht (WebSocket, personalisierte UI, Profil) hätte das gleiche Problem.

### Korrekter Fix

1. **AuthProvider Component** erstellen (Client Component)
2. Im Root-Layout (`app/layout.tsx`) einbinden, um alle geschützten Routen wrappen
3. Der Provider ruft `loadUser()` beim Mount auf
4. `loadUser()` wird **nicht** aus dem Provider entfernt — er bleibt die zentrale Stelle
5. Der Workaround in SessionPanel kann dann entfernt werden

```typescript
// components/shared/AuthProvider.tsx
"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/lib/stores/authStore";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);
  const isLoading = useAuthStore((s) => s.isLoading);
  const loadUser = useAuthStore((s) => s.loadUser);

  useEffect(() => {
    if (!user && !isLoading) {
      loadUser();
    }
  }, [user, isLoading, loadUser]);

  return <>{children}</>;
}
```

```typescript
// app/layout.tsx — add AuthProvider
import { AuthProvider } from "@/components/shared/AuthProvider";

// ... im return:
<QueryProvider>
  <ThemeProvider />
  <AuthProvider>
    {children}
  </AuthProvider>
</QueryProvider>
```

### Resolution Criteria

- [ ] `AuthProvider` Component erstellt
- [ ] In Root-Layout eingebunden
- [ ] Workaround in SessionPanel entfernt
- [ ] `user.id` nach Page Reload in allen Komponenten verfügbar
- [ ] Integration Test: Page Reload → WebSocket verbindet korrekt
