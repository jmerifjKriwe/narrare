import { create } from "zustand";
import { authApi, clearAccessToken, setAccessToken } from "@/lib/api/client";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;

  login: (email: string, password: string) => Promise<User>;
  register: (email: string, password: string, displayName?: string) => Promise<User>;
  logout: () => void;
  loadUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: false,
  isAuthenticated: false,

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

  logout: () => {
    clearAccessToken();
    set({ user: null, isAuthenticated: false });
    window.location.href = "/login";
  },

  loadUser: async () => {
    set({ isLoading: true });
    try {
      const user = await authApi.me();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },
}));
