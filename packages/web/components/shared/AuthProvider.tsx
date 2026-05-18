"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/lib/stores/authStore";

/**
 * Hydrates the auth store on app mount.
 *
 * After a page reload, the in-memory access token and user object are gone.
 * This component calls loadUser() which restores the session via httpOnly
 * refresh cookie and populates the store.
 */
export function AuthProvider({ children }: { readonly children: React.ReactNode }) {
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
