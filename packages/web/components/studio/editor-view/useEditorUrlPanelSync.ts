import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo } from "react";
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
 * param. Reads the URL on mount (URL → store) and writes the store value back
 * to the URL when it changes (store → URL).
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

  // URL → store: open the panel indicated by the URL on mount
  useEffect(() => {
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
    const nextParams = setOptionalSearchParam(currentParams, "panel", serializedPanel);
    router.replace(searchParamsHref(pathname, nextParams), { scroll: false });
  }, [activeRightPanel, parsedUrlPanel, pathname, router, searchParamsSnapshot]);
}
