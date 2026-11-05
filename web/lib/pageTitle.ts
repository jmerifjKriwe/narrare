import {
  createContext,
  createElement,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { t } from "./i18n";

/**
 * The tab's name (WCAG 2.4.2): a page says who it is, the document wears
 * `<page> — Narrare` for as long as that page is showing, and the shell's
 * hook publishes the page's own name to the top bar (P9's breadcrumb). The
 * page's `h1` stays in the page body — one heading per page is its own
 * constraint; the tab is the tab.
 *
 * The document title is one global and pages are many, so the wearing title
 * is a stack, not an assignment. Each `usePageTitle` effect pushes its page
 * and the document wears the top; unmount pops and re-wears. A descendant's
 * effects run before its ancestor's, so a page whose pane also names itself
 * (the workspace and a dock panel) is pushed last and keeps the tab — the
 * workspace is the page, the pane is a pane. A naive capture-and-restore
 * effect would leak exactly there: the page's effect would capture the
 * pane's title as its "previous" one and restore a stale name. The first
 * push captures what the document wore before any page claimed it, and the
 * pop that empties the stack puts that back — so two providers in a row
 * start from a clean capture, not the first provider's leftover.
 */

/** `<page> — Narrare`: the page's name and the app's, composed at wear time
 * so the app's half always renders through the current catalog. */
function compose(page: string): string {
  return `${page} — ${t("app.title")}`;
}

type Entry = { name: string };
const stack: Entry[] = [];
let beforePages: string | null = null;

function wear(): void {
  const top = stack[stack.length - 1];
  document.title = top === undefined ? (beforePages ?? t("app.title")) : compose(top.name);
}

/** The page name the tab wears now — the value the top bar shows. */
function topName(): string | null {
  const top = stack[stack.length - 1];
  return top === undefined ? null : top.name;
}

function pushPage(name: string): () => void {
  const entry = { name };
  if (stack.length === 0) beforePages = document.title;
  stack.push(entry);
  wear();
  return () => {
    // Own entry, not the name: the same name can be pushed twice (a nested
    // page with the same title), and each pop must take only its own.
    const at = stack.indexOf(entry);
    if (at !== -1) stack.splice(at, 1);
    if (stack.length === 0) {
      document.title = beforePages ?? t("app.title");
      beforePages = null;
    } else {
      wear();
    }
  };
}

/**
 * The shell's floor for the tab's name, called on boot and on a language
 * change: the app's own name when no page is showing, and a recomposition
 * of the wearing page's title when one is — a language switch must not
 * strip the page's name out of the tab.
 */
export function applyBaseTitle(): void {
  wear();
}

const PageTitleContext = createContext<string | null>(null);
const PageTitleSetterContext = createContext<((name: string | null) => void) | null>(null);

/**
 * Mounts the page-title surface for a subtree: pages under it publish
 * through `usePageTitle`, and the top bar under it reads through
 * `usePageTitleValue`. The published value mirrors the stack's top, so
 * nested pushers settle the same way the document title does.
 */
export function PageTitleProvider({ children }: { children: ReactNode }) {
  const [pageTitle, setPageTitle] = useState<string | null>(null);
  return createElement(
    PageTitleSetterContext.Provider,
    { value: setPageTitle },
    createElement(PageTitleContext.Provider, { value: pageTitle }, children),
  );
}

/** The name of the page that is showing, for the top bar's place indicator. */
export function usePageTitleValue(): string | null {
  return useContext(PageTitleContext);
}

/**
 * Names the page this hook renders in: the document wears `${title} —
 * Narrare` until the page goes, then hands back what was there before. A
 * new title string re-wears in place; unmount restores. Call it once per
 * page — the hook is the page's signature, not a per-component concern.
 */
export function usePageTitle(title: string): void {
  const publish = useContext(PageTitleSetterContext);
  useEffect(() => {
    const pop = pushPage(title);
    // The stack's top, not `title`: with nested pushers the outer page
    // pushed last and its name is what both the tab and the bar should say.
    publish?.(topName());
    return () => {
      pop();
      publish?.(topName());
    };
  }, [title, publish]);
}
