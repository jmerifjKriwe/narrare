// @vitest-environment jsdom
/**
 * The tab's name, as the pages will set it: `usePageTitle` wears `<page> —
 * Narrare` for as long as its page is showing and hands the document back
 * exactly what it wore before the page arrived. The contract is a stack, not
 * an assignment — React runs a descendant's effects before its ancestor's,
 * so a page whose pane also names itself would hand a naive
 * capture-and-restore implementation the pane's title as its "previous"
 * title, and the page's unmount would restore a stale name. Two providers
 * in a row are the other leak this pins: whatever the first provider left
 * behind must not become the second one's restore base.
 *
 * The provider's publish is asserted from the outside, the way P9's top bar
 * will read it: `usePageTitleValue` names the page, not the composed title —
 * the bar shows the place, the tab shows the place and the app.
 */
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PageTitleProvider, usePageTitle, usePageTitleValue } from "./pageTitle";

/** A page: it names itself once, the way every page will. */
function Page({ title }: { title: string }) {
  usePageTitle(title);
  return null;
}

afterEach(() => {
  cleanup();
  document.title = "";
});

describe("usePageTitle", () => {
  it("wears `<page> — Narrare` and restores the previous title on unmount", () => {
    document.title = "Vorher";
    const view = render(
      <PageTitleProvider>
        <Page title="Romane" />
      </PageTitleProvider>,
    );

    expect(document.title).toBe("Romane — Narrare");

    view.unmount();
    expect(document.title).toBe("Vorher");
  });

  it("two providers in a row do not leak the first page's title", () => {
    document.title = "Vorher";
    const first = render(
      <PageTitleProvider>
        <Page title="Romane" />
      </PageTitleProvider>,
    );
    first.unmount();

    const second = render(
      <PageTitleProvider>
        <Page title="Wissen" />
      </PageTitleProvider>,
    );
    expect(document.title).toBe("Wissen — Narrare");

    second.unmount();
    expect(document.title).toBe("Vorher");
  });

  it("keeps the page's name when a pane it renders names itself", () => {
    // The workspace shape: the page (ancestor) calls the hook and renders a
    // dock pane (descendant) that calls it too. Effects run child-first, so
    // the pane pushed first and the page pushed last — the stack's top, what
    // the tab wears, is the page's name; the pane is a pane, not the page.
    function Workspace() {
      usePageTitle("Romane");
      return <Pane />;
    }
    function Pane() {
      usePageTitle("Chat");
      return null;
    }

    document.title = "Vorher";
    const view = render(
      <PageTitleProvider>
        <Workspace />
      </PageTitleProvider>,
    );

    expect(document.title).toBe("Romane — Narrare");

    view.unmount();
    expect(document.title).toBe("Vorher");
  });

  it("publishes the page's name for the top bar", () => {
    let shown: string | null | undefined;
    function Bar() {
      shown = usePageTitleValue();
      return null;
    }

    document.title = "Vorher";
    const view = render(
      <PageTitleProvider>
        <Bar />
        <Page title="Romane" />
      </PageTitleProvider>,
    );

    expect(shown).toBe("Romane");

    view.unmount();
  });
});
