import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef } from "react";
import type {
  EditorRightPanelId,
  EditorRightPanelRequestSource,
} from "@/lib/stores/editorRightPanelState";
import { searchParamsHref, setOptionalSearchParam } from "@/lib/url-state/searchParams";
import {
  parseEditorRightPanelParam,
  serializeEditorRightPanelParam,
} from "./editorRightPanelUrlState";

interface UseEditorUrlPanelSyncOptions {
  activeRightPanel: EditorRightPanelId | null;
  openRightPanel: (panel: EditorRightPanelId, source: EditorRightPanelRequestSource) => void;
}

/**
 * Two-way sync between the active right panel state and the URL `panel` query
 * param. Reads the URL (URL → store) and writes the store value back to the
 * URL (store → URL).
 *
 * Both directions need echo suppression because `router.replace` is
 * asynchronous: a write scheduled for an older store state can land AFTER the
 * store has moved on, and naively reading it back would clobber the new
 * state. Symptom this guards against (found by the ADR-084 E2E): clicking
 * "Start Session" right after opening the generation panel — the pending
 * `?panel=generation` replace landed while the session panel was already
 * active, re-opened the generation panel, and unmounted the freshly
 * connected SessionPanel (its WebSocket closed right after
 * `session_created`).
 */
export function useEditorUrlPanelSync({
  activeRightPanel,
  openRightPanel,
}: UseEditorUrlPanelSyncOptions) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchParamsSnapshot = searchParams.toString();
  const parsedUrlPanel = useMemo(
    () => parseEditorRightPanelParam(new URLSearchParams(searchParamsSnapshot).get("panel")),
    [searchParamsSnapshot],
  );

  // Last URL panel this hook applied to the store (undefined = never applied).
  // Guards the URL→store effect against re-running on STORE-driven changes
  // of `activeRightPanel` (the param is stale until the router.replace lands).
  const appliedUrlPanelRef = useRef<EditorRightPanelId | null | undefined>(undefined);

  // Last panel value this hook wrote to the URL (undefined = never written).
  // A param change that equals our own last write is an ECHO of that write
  // landing asynchronously — never user intent, so it must not reopen a panel
  // the store has since moved away from. (string, not EditorRightPanelId:
  // `serializeEditorRightPanelParam` returns the raw param value.)
  const lastWrittenPanelRef = useRef<string | null | undefined>(undefined);

  // URL → store: open the panel indicated by the URL on mount or when the
  // URL panel param itself changes (browser navigation / manual edit) — but
  // never apply our own pending write echoing back.
  useEffect(() => {
    if (parsedUrlPanel === lastWrittenPanelRef.current) return;
    if (appliedUrlPanelRef.current === parsedUrlPanel) return;
    appliedUrlPanelRef.current = parsedUrlPanel;
    if (parsedUrlPanel !== null && activeRightPanel !== parsedUrlPanel) {
      openRightPanel(parsedUrlPanel, "url");
    }
  }, [activeRightPanel, openRightPanel, parsedUrlPanel]);

  // store → URL: write the active panel back to the URL
  useEffect(() => {
    if (parsedUrlPanel !== null && activeRightPanel !== parsedUrlPanel) return;
    const currentParams = new URLSearchParams(searchParamsSnapshot);
    const serializedPanel = serializeEditorRightPanelParam(activeRightPanel);
    if (currentParams.get("panel") === serializedPanel) return;
    lastWrittenPanelRef.current = serializedPanel;
    const nextParams = setOptionalSearchParam(currentParams, "panel", serializedPanel);
    router.replace(searchParamsHref(pathname, nextParams), { scroll: false });
  }, [activeRightPanel, parsedUrlPanel, pathname, router, searchParamsSnapshot]);
}
