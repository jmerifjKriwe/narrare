"use client";

import { useEffect, useState } from "react";
import { useThemeStore } from "@/lib/stores/themeStore";

export function ThemeProvider() {
  const theme = useThemeStore((s) => s.theme);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;

    if (theme === "neutral") {
      document.documentElement.setAttribute("data-theme", "neutral");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  }, [theme, mounted]);

  // Return null because this is just a logic component, not a wrapper
  // that renders UI elements itself. It just modifies the html tag.
  return null;
}
