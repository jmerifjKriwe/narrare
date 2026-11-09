// @vitest-environment jsdom
/**
 * The one sentence a dead stream says: the frame's code picks it — the
 * generic one for a code (or payload) that names nothing actionable — and
 * the provider's own message hides behind a details disclosure, never in the
 * headline. The link's words inside every sentence are the settings door.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { t } from "@shell/lib/i18n";

import { StreamError } from "./StreamError";

afterEach(cleanup);

describe("StreamError's sentence", () => {
  it("a missing model names the row to fix and points at the settings", () => {
    render(
      <StreamError failure={{ code: "model-not-found", model: "glm-5.3", detail: "404" }} />,
    );
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain(
      t("errors.modelNotFound", { model: "glm-5.3", link: t("errors.link") }),
    );
    const link = screen.getByRole("link", { name: t("errors.link") });
    expect(link.getAttribute("href")).toBe("/settings/provider");
  });

  it.each([
    [{ code: "provider-auth", detail: "401" }, "errors.providerAuth"],
    [{ code: "key-unavailable" }, "errors.keyUnavailable"],
    [{ code: "prompt-refused" }, "errors.promptRefused"],
  ] as const)("the %s frame speaks its own sentence", (failure, key) => {
    render(<StreamError failure={failure} />);
    expect(screen.getByRole("alert").textContent).toContain(t(key, { link: t("errors.link") }));
  });

  it("a code the app does not know — and no code at all — read as the generic", () => {
    const generic = t("errors.unknown", { link: t("errors.link") });
    const { unmount } = render(<StreamError failure={{ code: "something-new" }} />);
    expect(screen.getByRole("alert").textContent).toContain(generic);
    unmount();
    render(<StreamError failure={{}} />);
    expect(screen.getByRole("alert").textContent).toContain(generic);
  });

  it("a model-less model-not-found cannot name a row: the generic speaks", () => {
    render(<StreamError failure={{ code: "model-not-found" }} />);
    expect(screen.getByRole("alert").textContent).toContain(
      t("errors.unknown", { link: t("errors.link") }),
    );
  });

  it("the provider's own message hides behind a disclosure, off by default", () => {
    const { container, unmount } = render(
      <StreamError failure={{ code: "unknown", detail: "the endpoint answered 502" }} />,
    );
    const disclosure = container.querySelector("details");
    expect(disclosure).not.toBeNull();
    expect(disclosure!.querySelector("summary")!.textContent).toBe(t("errors.details"));
    expect(disclosure!.textContent).toContain("the endpoint answered 502");
    expect(disclosure!.hasAttribute("open")).toBe(false); // closed until the reader opens it
    unmount();

    // No detail in the frame, no disclosure at all — this render's own
    // container, not the unmount-emptied first one.
    const { container: second } = render(
      <StreamError failure={{ code: "key-unavailable" }} />,
    );
    expect(second.querySelector("details")).toBeNull();
  });
});
