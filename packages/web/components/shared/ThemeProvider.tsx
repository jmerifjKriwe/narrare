"use client";

import { useEffect, useState } from "react";
import { useThemeStore } from "@/lib/stores/themeStore";
import type { ColorMode } from "@/lib/stores/themeStore";

function applyColorMode(mode: ColorMode) {
  const root = document.documentElement;

  if (mode === "dark") {
    root.classList.add("dark");
  } else if (mode === "light") {
    root.classList.remove("dark");
  } else {
    // system
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    root.classList.toggle("dark", prefersDark);
  }
}

export function ThemeProvider() {
  const colorMode = useThemeStore((s) => s.colorMode);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    applyColorMode(colorMode);
  }, [colorMode, mounted]);

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

  // Return null — this component only modifies the <html> class
  return null;
}
