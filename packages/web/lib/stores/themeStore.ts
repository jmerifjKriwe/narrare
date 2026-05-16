import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ColorMode = "light" | "dark" | "system";

interface ThemeState {
  colorMode: ColorMode;
  setColorMode: (mode: ColorMode) => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      colorMode: "system",
      setColorMode: (colorMode) => set({ colorMode }),
    }),
    { name: "narrare-theme" },
  ),
);
