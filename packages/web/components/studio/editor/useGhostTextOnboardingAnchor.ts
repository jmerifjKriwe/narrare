import type { Editor } from "@tiptap/react";
import { useEffect, useState } from "react";

interface UseGhostTextOnboardingAnchorParams {
  editor: Editor | null;
  showOnboarding: boolean;
}

/**
 * Tracks the DOM element used to anchor the ghost-text onboarding callout.
 *
 * Owns a single responsibility: while onboarding is active, observe the editor
 * DOM for the first `.ghost-text-suggestion` element and expose it as the
 * anchor (or null) so the host can render the coaching callout positioned
 * against it.
 */
export function useGhostTextOnboardingAnchor({
  editor,
  showOnboarding,
}: UseGhostTextOnboardingAnchorParams) {
  const [onboardingAnchor, setOnboardingAnchor] = useState<HTMLElement | null>(null);

  useEffect(() => {
    if (!showOnboarding || !editor) return;
    const checkForGhostText = () => {
      const ghostEl = document.querySelector(".ghost-text-suggestion");
      if (ghostEl) setOnboardingAnchor(ghostEl as HTMLElement);
    };
    const observer = new MutationObserver(checkForGhostText);
    observer.observe(editor.view.dom, { childList: true, subtree: true });
    const handler = () => {
      setTimeout(checkForGhostText, 50);
    };
    editor.on("update", handler);
    editor.on("transaction", handler);
    return () => {
      observer.disconnect();
      editor.off("update", handler);
      editor.off("transaction", handler);
    };
  }, [editor, showOnboarding]);

  return onboardingAnchor;
}
