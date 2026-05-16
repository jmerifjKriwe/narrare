import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ColorMode = "light" | "dark" | "system";
export type ThemeName = "neutral" | "narrare"; // extend as themes are added

interface ThemeState {
  theme: ThemeName;
  colorMode: ColorMode;
  setTheme: (theme: ThemeName) => void;
  setColorMode: (mode: ColorMode) => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      theme: "neutral",
      colorMode: "system",
      setTheme: (theme) => set({ theme }),
      setColorMode: (colorMode) => set({ colorMode }),
    }),
    { name: "narrare-theme" },
  ),
);
