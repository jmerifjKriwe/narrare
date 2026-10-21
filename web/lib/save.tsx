"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { t } from "./i18n";

export type SaveStatus = "idle" | "saving" | "saved";

const DELAY_MS = 800;

/**
 * Debounced save: one request per typing pause, one more when the editor goes away.
 * The endpoint is idempotent, so a duplicate flush costs nothing.
 */
export function useAutosave(
  chapterId: string | null,
  onSaved?: (chapterId: string, body: string) => void,
) {
  const [status, setStatus] = useState<SaveStatus>("idle");
  const timer = useRef<number | null>(null);
  const pending = useRef<string | null>(null);
  const id = useRef(chapterId);
  id.current = chapterId;
  const saved = useRef(onSaved);
  saved.current = onSaved;

  const flush = useCallback(async () => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    const body = pending.current;
    const target = id.current;
    if (body === null || target === null) return;
    pending.current = null;
    setStatus("saving");
    await fetch(`/api/writing/chapters/${target}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body }),
    });
    setStatus("saved");
    saved.current?.(target, body);
  }, []);

  const schedule = useCallback(
    (body: string) => {
      pending.current = body;
      setStatus("idle");
      if (timer.current !== null) clearTimeout(timer.current);
      timer.current = window.setTimeout(() => void flush(), DELAY_MS);
    },
    [flush],
  );

  useEffect(() => {
    function onHidden() {
      if (document.visibilityState === "hidden") void flush();
    }
    window.addEventListener("beforeunload", flush);
    document.addEventListener("visibilitychange", onHidden);
    return () => {
      window.removeEventListener("beforeunload", flush);
      document.removeEventListener("visibilitychange", onHidden);
      void flush();
    };
  }, [flush]);

  return { status, schedule, flush };
}

export function SaveIndicator({ status }: { status: SaveStatus }) {
  if (status === "idle") return null;
  return <span role="status">{t(status === "saving" ? "save.saving" : "save.saved")}</span>;
}
