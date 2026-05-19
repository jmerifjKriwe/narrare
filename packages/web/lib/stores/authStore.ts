import { create } from "zustand";
import {
  authApi,
  clearAccessToken,
  getAccessToken,
  logoutApi,
  restoreSession,
  setAccessToken,
} from "@/lib/api/client";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  /** Guards against duplicate session checks in AuthProvider.
   *  Set to true once loadUser() reaches a terminal state (success or failure). */
  _sessionChecked: boolean;

  login: (email: string, password: string) => Promise<User>;
  register: (email: string, password: string, displayName?: string) => Promise<User>;
  logout: () => void;
  loadUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: false,
  isAuthenticated: false,
  _sessionChecked: false,

  login: async (email, password) => {
    set({ isLoading: true });
    try {
      const tokens = await authApi.login(email, password);
      setAccessToken(tokens.access_token);
      const user = await authApi.me();
      set({ user, isAuthenticated: true, isLoading: false });
      return user;
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  register: async (email, password, displayName = "") => {
    set({ isLoading: true });
    try {
      const tokens = await authApi.register(email, password, displayName);
      setAccessToken(tokens.access_token);
      const user = await authApi.me();
      set({ user, isAuthenticated: true, isLoading: false });
      return user;
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  logout: async () => {
    try {
      await logoutApi();
    } catch {
      // Ignore — we still clear local state
    }
    clearAccessToken();
    set({ user: null, isAuthenticated: false, _sessionChecked: false });
    window.location.href = "/login";
  },

  loadUser: async () => {
    if (useAuthStore.getState()._sessionChecked) return; // re-entrancy guard
    set({ isLoading: true });
    try {
      // Try to restore session via httpOnly refresh cookie (e.g. after F5)
      if (!getAccessToken()) {
        const restored = await restoreSession();
        if (!restored) {
          set({ user: null, isAuthenticated: false, isLoading: false, _sessionChecked: true });
          return; // skip me() if restore failed — avoids a guaranteed 401
        }
      }
      const user = await authApi.me();
      set({ user, isAuthenticated: true, isLoading: false, _sessionChecked: true });
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false, _sessionChecked: true });
    }
  },
}));
