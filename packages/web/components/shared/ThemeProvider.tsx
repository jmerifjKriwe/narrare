"use client";

import { useEffect, useState } from "react";
import type { ColorMode, ThemeName } from "@/lib/stores/themeStore";
import { useThemeStore } from "@/lib/stores/themeStore";

function applyTheme(theme: ThemeName, colorMode: ColorMode) {
  const root = document.documentElement;

  // Set theme attribute
  root.setAttribute("data-theme", theme);

  // Set dark mode class
  if (colorMode === "dark") {
    root.classList.add("dark");
  } else if (colorMode === "light") {
    root.classList.remove("dark");
  } else {
    // system
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    root.classList.toggle("dark", prefersDark);
  }
}

export function ThemeProvider() {
  const theme = useThemeStore((s) => s.theme);
  const colorMode = useThemeStore((s) => s.colorMode);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    applyTheme(theme, colorMode);
  }, [theme, colorMode, mounted]);

  // Listen for system preference changes when mode is "system"
  useEffect(() => {
    if (!mounted || colorMode !== "system") return;
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => {
      document.documentElement.classList.toggle("dark", e.matches);
    };
    mediaQuery.addEventListener("change", handler);
    return () => mediaQuery.removeEventListener("change", handler);
  }, [colorMode, mounted]);

  return null;
}
