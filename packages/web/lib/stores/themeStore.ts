import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Theme = "pergament" | "neutral";

interface ThemeState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      theme: "pergament", // Default theme
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: "narrare-theme", // Local storage key
    },
  ),
);
