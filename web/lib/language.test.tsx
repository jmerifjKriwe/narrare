// @vitest-environment jsdom
/**
 * The one language contract (D17, shelf row 12 / #892): the switcher UI,
 * the keyboard contract and the refusal restore, owned once in the shell.
 * The welcome's and the wizard's pre-setup radio faces and the chrome's
 * post-setup chip (variante A, the light chrome draft's tile 5) are faces
 * of this one home — the doors' behavior is preserved here, and the chip
 * adds the menu face without a second contract.
 *
 * Only the API client is mocked at its module boundary; the mock keeps the
 * backend's own contract: before setup the user row does not exist, so
 * `PATCH /api/settings` refuses with 409 "setup required"
 * (settings/service.py). The locale store, the mirror and the query cache
 * are real — the contract is their composition, not a mock's behavior.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api/client", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(),
    PATCH: vi.fn(),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

import { client } from "./api/client";
import { LanguageChip, LanguageSwitcher, useLanguageChoice } from "./language";
import { activeLocale, applyLocale, chosenLocale } from "./locale";
import { readPreSetupLocale, storePreSetupLocale } from "./preSetupLocale";
import { queryClient, useSettings, useSettingsQuery } from "./query";
import { de } from "./test/catalogs";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

function ok(): Response {
  return new Response(null, { status: 200 });
}

/** The mock instance's state: setup creates the user row, and only then can
 *  the settings write land — the backend's own sequence. */
let setUp: boolean;
let storedLocale: string | null;

function scriptApi() {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") {
      return { data: { locale: storedLocale, theme: null }, response: ok() };
    }
    throw new Error(`unexpected request: ${path}`);
  });
  api.PATCH.mockImplementation(async (path: string, init?: { body?: { locale?: string | null } }) => {
    if (path !== "/api/settings") throw new Error(`unexpected request: ${path}`);
    if (!setUp) {
      return { error: { detail: "setup required" }, response: new Response(null, { status: 409 }) };
    }
    storedLocale = init?.body?.locale ?? null;
    return { data: { locale: storedLocale, theme: null }, response: ok() };
  });
}

const settingsReads = () => api.GET.mock.calls.filter(([path]) => path === "/api/settings").length;

/** The shell always observes the settings row (the boot gate reads it) —
 *  invalidation refetches only with an observer, so the contract's faces
 *  render beside one. It observes, it does not adopt: adoption is the
 *  boot's own effect, and the mirror tests own the store here. */
function SettingsProbe() {
  useSettingsQuery();
  return null;
}

beforeEach(() => {
  setUp = false;
  storedLocale = null;
  scriptApi();
  localStorage.clear();
  // The German visitor: the browser speaks de-DE, the row holds nothing yet.
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  applyLocale(null);
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  applyLocale(null);
  localStorage.clear();
});

describe("the radio face — the draft's DE|EN|FR group", () => {
  it("draws the design's order with endonym names and one tab stop", () => {
    applyLocale("de");
    render(<LanguageSwitcher variant="welcome" preSetup />);

    const group = screen.getByRole("radiogroup", { name: de["shell.language"] });
    const radios = within(group).getAllByRole("radio");
    expect(radios.map((radio) => radio.textContent)).toEqual(["DE", "EN", "FR"]);
    expect(radios.map((radio) => radio.getAttribute("aria-label"))).toEqual([
      "Deutsch",
      "English",
      "Français",
    ]);
    expect(radios.map((radio) => radio.getAttribute("aria-checked"))).toEqual([
      "true",
      "false",
      "false",
    ]);
    expect(radios.map((radio) => radio.tabIndex)).toEqual([0, -1, -1]);
  });

  it("cycles with the arrows, wrapping, and focus follows the choice", async () => {
    setUp = true;
    applyLocale("de");
    render(<LanguageSwitcher variant="welcome" preSetup />);

    const radio = (name: string) => screen.getByRole("radio", { name });
    radio("Deutsch").focus();
    fireEvent.keyDown(radio("Deutsch"), { key: "ArrowRight" });
    await waitFor(() => expect(radio("English").getAttribute("aria-checked")).toBe("true"));
    expect(document.activeElement).toBe(radio("English"));

    // Wrap at the left end: DE's left neighbour is FR, the draft's last.
    fireEvent.keyDown(radio("Deutsch"), { key: "ArrowLeft" });
    await waitFor(() => expect(radio("Français").getAttribute("aria-checked")).toBe("true"));
    expect(document.activeElement).toBe(radio("Français"));

    // Home returns to the draft's lead; the tab stop travels with it.
    fireEvent.keyDown(radio("Français"), { key: "Home" });
    await waitFor(() => expect(radio("Deutsch").getAttribute("aria-checked")).toBe("true"));
    expect(radio("Deutsch").tabIndex).toBe(0);
    expect(radio("English").tabIndex).toBe(-1);

    // End jumps to the last; ArrowUp walks back, ArrowDown forward.
    fireEvent.keyDown(radio("Deutsch"), { key: "End" });
    await waitFor(() => expect(radio("Français").getAttribute("aria-checked")).toBe("true"));
    fireEvent.keyDown(radio("Français"), { key: "ArrowUp" });
    await waitFor(() => expect(radio("English").getAttribute("aria-checked")).toBe("true"));
    fireEvent.keyDown(radio("English"), { key: "ArrowDown" });
    await waitFor(() => expect(radio("Français").getAttribute("aria-checked")).toBe("true"));
  });

  it("Space and Enter select the focused radio — the wizard's contract", async () => {
    setUp = true;
    applyLocale("de");
    render(<LanguageSwitcher variant="wizard" preSetup />);

    const radio = (name: string) => screen.getByRole("radio", { name });
    fireEvent.keyDown(radio("Deutsch"), { key: " " });
    // The focused radio is the active one: no write is owed.
    expect(api.PATCH).not.toHaveBeenCalled();

    radio("English").focus();
    fireEvent.keyDown(radio("English"), { key: "Enter" });
    await waitFor(() => expect(radio("English").getAttribute("aria-checked")).toBe("true"));
    expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "en" } });
    expect(document.activeElement).toBe(radio("English"));
  });

  it("clicking the active radio changes nothing and writes nothing", () => {
    applyLocale("de");
    render(<LanguageSwitcher variant="welcome" preSetup />);

    fireEvent.click(screen.getByRole("radio", { name: "Deutsch" }));
    expect(api.PATCH).not.toHaveBeenCalled();
    expect(activeLocale()).toBe("de");
  });

  it("keeps each door's drafted face — the welcome's separators, the wizard's none", () => {
    applyLocale("de");
    const { unmount } = render(<LanguageSwitcher variant="welcome" preSetup />);
    const welcome = screen.getByRole("radiogroup", { name: de["shell.language"] });
    // Three radios and the two hairline separators between them.
    expect(welcome.childElementCount).toBe(5);
    unmount();

    render(<LanguageSwitcher variant="wizard" preSetup />);
    const wizard = screen.getByRole("radiogroup", { name: de["shell.language"] });
    expect(wizard.childElementCount).toBe(3);
  });
});

describe("the pre-setup contract — the mirror stands until the row can hold it", () => {
  it("adopts the mirrored language before paint when the row holds no choice", () => {
    storePreSetupLocale("fr");
    render(<LanguageSwitcher variant="welcome" preSetup />);

    // The layout effect ran during the commit: the first paint is French,
    // never a flash of the browser's language past the mirror.
    expect(activeLocale()).toBe("fr");
    expect(screen.getByRole("radio", { name: "Français" }).getAttribute("aria-checked")).toBe("true");
  });

  it("does not adopt the mirror when the row already holds a choice", () => {
    storePreSetupLocale("fr");
    applyLocale("de");
    render(<LanguageSwitcher variant="welcome" preSetup />);

    expect(activeLocale()).toBe("de");
    expect(readPreSetupLocale()).toBe("fr"); // the mirror stands untouched
  });

  it("applies at once, attempts the write, keeps the choice on the structural 409", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <SettingsProbe />
        <LanguageSwitcher variant="welcome" preSetup />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole("radio", { name: "English" }));
    expect(activeLocale()).toBe("en"); // applied before the answer lands
    await waitFor(() => expect(readPreSetupLocale()).toBe("en"));
    expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "en" } });
    expect(chosenLocale()).toBe("en");
    expect(screen.getByRole("radio", { name: "English" }).getAttribute("aria-checked")).toBe("true");
    // The row could not take the write, so no settings refetch is owed —
    // the probe's boot read stands alone.
    expect(settingsReads()).toBe(1);
  });

  it("a landed write clears the mirror and refreshes the cached row", async () => {
    setUp = true;
    render(
      <QueryClientProvider client={queryClient}>
        <SettingsProbe />
        <LanguageSwitcher variant="welcome" preSetup />
      </QueryClientProvider>,
    );

    // The boot gate opens on the settled row — the page renders after it.
    await waitFor(() => expect(queryClient.getQueryState(["settings"])?.status).toBe("success"));
    const before = settingsReads();
    fireEvent.click(screen.getByRole("radio", { name: "English" }));
    await waitFor(() => expect(readPreSetupLocale()).toBeNull());
    expect(storedLocale).toBe("en");
    await waitFor(() => expect(settingsReads()).toBeGreaterThan(before));
    expect(activeLocale()).toBe("en");
  });

  it("any other refusal restores the prior choice and its mirror", async () => {
    storePreSetupLocale("de");
    render(<LanguageSwitcher variant="welcome" preSetup />);

    api.PATCH.mockResolvedValueOnce({
      error: { detail: "refused" },
      response: new Response(null, { status: 503 }),
    });
    fireEvent.click(screen.getByRole("radio", { name: "English" }));

    await waitFor(() => expect(activeLocale()).toBe("de"));
    expect(chosenLocale()).toBe("de");
    expect(readPreSetupLocale()).toBe("de");
    expect(screen.getByRole("radio", { name: "Deutsch" }).getAttribute("aria-checked")).toBe("true");
  });

  it("a network failure restores the prior choice too", async () => {
    storePreSetupLocale("de");
    render(<LanguageSwitcher variant="wizard" preSetup />);

    api.PATCH.mockRejectedValueOnce(new Error("offline"));
    fireEvent.click(screen.getByRole("radio", { name: "Français" }));

    await waitFor(() => expect(activeLocale()).toBe("de"));
    expect(readPreSetupLocale()).toBe("de");
  });
});

describe("the post-setup contract — the row is the record, no mirror", () => {
  it("writes the row without touching the mirror and refreshes the cache", async () => {
    setUp = true;
    applyLocale("de");
    render(
      <QueryClientProvider client={queryClient}>
        <SettingsProbe />
        <LanguageSwitcher variant="welcome" />
      </QueryClientProvider>,
    );

    // The boot gate opens on the settled row — the page renders after it.
    await waitFor(() => expect(queryClient.getQueryState(["settings"])?.status).toBe("success"));
    const before = settingsReads();
    fireEvent.click(screen.getByRole("radio", { name: "English" }));
    await waitFor(() => expect(storedLocale).toBe("en"));
    expect(localStorage.getItem("narrare.locale.preSetup")).toBeNull();
    await waitFor(() => expect(settingsReads()).toBeGreaterThan(before));
  });

  it("a refusal restores the prior language — the structural 409 included", async () => {
    applyLocale("de");
    render(<LanguageSwitcher variant="welcome" />);

    // setUp is false: the write answers 409. Post-setup there is no mirror
    // to keep it — the shelf's contract restores like any other refusal.
    fireEvent.click(screen.getByRole("radio", { name: "English" }));
    await waitFor(() => expect(activeLocale()).toBe("de"));
    expect(localStorage.getItem("narrare.locale.preSetup")).toBeNull();
    expect(screen.getByRole("radio", { name: "Deutsch" }).getAttribute("aria-checked")).toBe("true");
  });
});

describe("the chrome chip — variante A, the real switcher (D17)", () => {
  it("names the active language and opens the draft's menu on click", async () => {
    setUp = true;
    applyLocale("de");
    render(<LanguageChip />);

    const trigger = screen.getByRole("button", { name: /Sprache/ });
    expect(trigger.textContent).toContain("DE (Deutsch)");
    expect(trigger.getAttribute("aria-haspopup")).toBe("menu");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(trigger);
    const menu = await screen.findByRole("menu", { name: de["shell.language"] });
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    const items = within(menu).getAllByRole("menuitemradio");
    expect(items.map((item) => item.getAttribute("aria-checked"))).toEqual([
      "true",
      "false",
      "false",
    ]);
    expect(items.map((item) => item.textContent)).toEqual([
      expect.stringContaining("Deutsch"),
      expect.stringContaining("English"),
      expect.stringContaining("Français"),
    ]);
    // Opening moves focus to the active row — the draft's checked lead.
    expect(document.activeElement).toBe(items[0]);
  });

  it("ArrowDown opens the menu; the arrows walk it with wrap, Home/End jump", async () => {
    setUp = true;
    applyLocale("de");
    render(<LanguageChip />);

    const trigger = screen.getByRole("button", { name: /Sprache/ });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    const menu = await screen.findByRole("menu");
    const items = within(menu).getAllByRole("menuitemradio");
    expect(document.activeElement).toBe(items[0]);

    fireEvent.keyDown(items[0], { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[1]);
    fireEvent.keyDown(items[1], { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[2]);
    // Wrap at the end; ArrowUp walks back.
    fireEvent.keyDown(items[2], { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[0]);
    fireEvent.keyDown(items[0], { key: "ArrowUp" });
    expect(document.activeElement).toBe(items[2]);
    fireEvent.keyDown(items[2], { key: "Home" });
    expect(document.activeElement).toBe(items[0]);
    fireEvent.keyDown(items[0], { key: "End" });
    expect(document.activeElement).toBe(items[2]);
    // Walking the menu focuses, it does not choose — Enter is the choice.
    expect(api.PATCH).not.toHaveBeenCalled();
  });

  it("Enter chooses, closes the menu and returns focus to the trigger", async () => {
    setUp = true;
    applyLocale("de");
    render(<LanguageChip />);

    const trigger = screen.getByRole("button", { name: /Sprache/ });
    fireEvent.click(trigger);
    const menu = await screen.findByRole("menu");
    const english = within(menu).getAllByRole("menuitemradio")[1];
    fireEvent.keyDown(english, { key: "Enter" });

    await waitFor(() => expect(activeLocale()).toBe("en"));
    expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "en" } });
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(trigger);
    expect(trigger.textContent).toContain("EN (English)");
    expect(storedLocale).toBe("en");
  });

  it("a click chooses too; Space on a row chooses", async () => {
    setUp = true;
    applyLocale("de");
    render(<LanguageChip />);

    // The trigger's accessible name speaks the active language — capture
    // the node once; it survives the re-renders a choice causes.
    const trigger = screen.getByRole("button", { name: /Sprache/ });
    fireEvent.click(trigger);
    const menu = await screen.findByRole("menu");
    fireEvent.click(within(menu).getAllByRole("menuitemradio")[2]);
    await waitFor(() => expect(activeLocale()).toBe("fr"));
    expect(screen.queryByRole("menu")).toBeNull();

    // Reopen and choose with Space.
    fireEvent.click(trigger);
    const again = await screen.findByRole("menu");
    fireEvent.keyDown(within(again).getAllByRole("menuitemradio")[0], { key: " " });
    await waitFor(() => expect(activeLocale()).toBe("de"));
  });

  it("Escape closes the menu and returns focus to the trigger", async () => {
    applyLocale("de");
    render(<LanguageChip />);

    const trigger = screen.getByRole("button", { name: /Sprache/ });
    fireEvent.click(trigger);
    await screen.findByRole("menu");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(trigger);
    expect(api.PATCH).not.toHaveBeenCalled();
  });

  it("an outside press closes without stealing focus", async () => {
    applyLocale("de");
    render(
      <div>
        <button type="button">outside</button>
        <LanguageChip />
      </div>,
    );

    const trigger = screen.getByRole("button", { name: /Sprache/ });
    fireEvent.click(trigger);
    await screen.findByRole("menu");
    const outside = screen.getByRole("button", { name: "outside" });
    outside.focus();
    fireEvent.mouseDown(outside);
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(outside);
  });

  it("a refused switch restores the prior language and the chip's face", async () => {
    applyLocale("de");
    render(<LanguageChip />);

    api.PATCH.mockResolvedValueOnce({
      error: { detail: "refused" },
      response: new Response(null, { status: 500 }),
    });
    fireEvent.click(screen.getByRole("button", { name: /Sprache/ }));
    const menu = await screen.findByRole("menu");
    fireEvent.click(within(menu).getAllByRole("menuitemradio")[1]);

    await waitFor(() => expect(activeLocale()).toBe("de"));
    expect(screen.getByRole("button", { name: /Sprache/ }).textContent).toContain("DE (Deutsch)");
    expect(localStorage.getItem("narrare.locale.preSetup")).toBeNull();
  });

  it("is the same contract as the radio face — one store, two faces", async () => {
    setUp = true;
    applyLocale("de");
    render(
      <div>
        <LanguageSwitcher variant="welcome" />
        <LanguageChip />
      </div>,
    );

    const trigger = screen.getByRole("button", { name: /Sprache/ });
    fireEvent.click(screen.getByRole("radio", { name: "English" }));
    await waitFor(() => expect(trigger.textContent).toContain("EN (English)"));
    expect(screen.getByRole("radio", { name: "English" }).getAttribute("aria-checked")).toBe("true");

    // And back through the chip: the radio follows the same choice.
    fireEvent.click(trigger);
    const menu = await screen.findByRole("menu");
    fireEvent.click(within(menu).getAllByRole("menuitemradio")[0]);
    await waitFor(() => expect(activeLocale()).toBe("de"));
    expect(screen.getByRole("radio", { name: "Deutsch" }).getAttribute("aria-checked")).toBe("true");
  });
});

// --- The null choice — „Dem Browser folgen“ (W7, the settings face) ---------

/**
 * The settings surface's checkbox rides the seam directly: this probe drives
 * `choose(null)` and `choose(locale)` the way the „Dem Browser folgen“
 * checkbox does, so the seam's own contract is what these pins hold — the
 * page's geometry lives in the settings capability's suite.
 */
function NullChoiceProbe({ preSetup = false }: { preSetup?: boolean } = {}) {
  const { locale, chosen, choose } = useLanguageChoice({ preSetup });
  return (
    <div>
      <p data-testid="active">{locale}</p>
      <p data-testid="chosen">{chosen === null ? "browser" : chosen}</p>
      <button type="button" onClick={() => void choose(null)}>
        follow
      </button>
      <button type="button" onClick={() => void choose("fr")}>
        fr
      </button>
    </div>
  );
}

describe("the null choice — „Dem Browser folgen“ (W7)", () => {
  it("hands the choice to the browser at once and writes {locale: null}", async () => {
    setUp = true;
    applyLocale("de");
    render(
      <QueryClientProvider client={queryClient}>
        <SettingsProbe />
        <NullChoiceProbe />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(queryClient.getQueryState(["settings"])?.status).toBe("success"));

    fireEvent.click(screen.getByRole("button", { name: "follow" }));
    expect(screen.getByTestId("chosen").textContent).toBe("browser"); // at once
    await waitFor(() =>
      expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: null } }),
    );
    expect(storedLocale).toBeNull();
  });

  it("the page speaks the browser's language from the null choice", async () => {
    setUp = true;
    applyLocale("de");
    // The browser reads French: following it means the page turns French.
    vi.stubGlobal("navigator", { language: "fr-FR", languages: ["fr-FR"] });
    render(
      <QueryClientProvider client={queryClient}>
        <NullChoiceProbe />
      </QueryClientProvider>,
    );
    expect(screen.getByTestId("active").textContent).toBe("de");

    fireEvent.click(screen.getByRole("button", { name: "follow" }));
    await waitFor(() => expect(screen.getByTestId("active").textContent).toBe("fr"));
  });

  it("a refusal restores the prior stored choice", async () => {
    setUp = true;
    applyLocale("de");
    vi.stubGlobal("navigator", { language: "fr-FR", languages: ["fr-FR"] });
    render(
      <QueryClientProvider client={queryClient}>
        <NullChoiceProbe />
      </QueryClientProvider>,
    );

    api.PATCH.mockResolvedValueOnce({
      error: { detail: "refused" },
      response: new Response(null, { status: 503 }),
    });
    fireEvent.click(screen.getByRole("button", { name: "follow" }));
    await waitFor(() => expect(screen.getByTestId("chosen").textContent).toBe("de"));
    expect(screen.getByTestId("active").textContent).toBe("de");
  });

  it("following twice writes once — the stored answer unchanged is no ask", () => {
    setUp = true;
    applyLocale(null);
    render(
      <QueryClientProvider client={queryClient}>
        <NullChoiceProbe />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "follow" }));
    expect(api.PATCH).not.toHaveBeenCalled();
  });

  it("a stored choice ends the browser follow — the checkbox's other half", async () => {
    setUp = true;
    applyLocale(null); // the browser decides
    render(
      <QueryClientProvider client={queryClient}>
        <NullChoiceProbe />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "fr" }));
    await waitFor(() => expect(screen.getByTestId("chosen").textContent).toBe("fr"));
    expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "fr" } });
  });

  it("pre-setup has no null face — the mirror contract answers nothing", () => {
    storePreSetupLocale("de");
    applyLocale("de");
    render(
      <QueryClientProvider client={queryClient}>
        <NullChoiceProbe preSetup />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "follow" }));
    expect(api.PATCH).not.toHaveBeenCalled();
    expect(readPreSetupLocale()).toBe("de"); // the mirror stands untouched
    expect(screen.getByTestId("chosen").textContent).toBe("de");
  });
});

// --- The optimistic cache patch — a choice stands before its refetch --------

/**
 * #939: the choice's write and its invalidation refetch take moments, and
 * both save surfaces (the profile form, the GoalSetter) read the row's
 * cache at click time. The choice must move the cached rows at choice
 * time — the strict `["settings", "read"]` entry whenever it holds a row,
 * the tolerant `["settings"]` entry when it carries a locale — so a save
 * in that window carries the pending choice, never the pre-switch answer.
 * `SaveSurfaceProbe` mounts both reads the way the surfaces do, and the
 * held GET keeps the choice's refetch in flight for the whole window.
 */

function SaveSurfaceProbe() {
  useSettings();
  useSettingsQuery();
  return null;
}

describe("the optimistic cache patch — a choice stands before its refetch (#939)", () => {
  /** Both reads answered, then the window: every further settings read
   *  hangs, exactly the in-flight state a save can click inside. */
  async function renderSurfacesHeld(face: ReactNode) {
    let held = false;
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings") {
        if (held) return new Promise(() => {});
        return { data: { locale: storedLocale, theme: null }, response: ok() };
      }
      throw new Error(`unexpected request: ${path}`);
    });
    render(
      <QueryClientProvider client={queryClient}>
        <SaveSurfaceProbe />
        {face}
      </QueryClientProvider>,
    );
    await waitFor(() => expect(queryClient.getQueryState(["settings", "read"])?.status).toBe("success"));
    await waitFor(() => expect(queryClient.getQueryState(["settings"])?.status).toBe("success"));
    held = true;
  }

  it("a choice stands in the cached rows before its refetch lands", async () => {
    setUp = true;
    storedLocale = "de";
    applyLocale("de");
    await renderSurfacesHeld(<LanguageSwitcher variant="welcome" />);

    fireEvent.click(screen.getByRole("radio", { name: "English" }));
    await waitFor(() =>
      expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "en" } }),
    );
    // The strict entry — both save surfaces' click-time source — and the
    // chrome's tolerant entry wear the pending choice already.
    expect(queryClient.getQueryData<{ locale: string | null }>(["settings", "read"])?.locale).toBe("en");
    expect(queryClient.getQueryData<{ locale: string | null }>(["settings"])?.locale).toBe("en");
  });

  it("the follow-browser null moves the cached rows too — the choice asserts the null", async () => {
    setUp = true;
    storedLocale = "de";
    applyLocale("de");
    await renderSurfacesHeld(<NullChoiceProbe />);

    fireEvent.click(screen.getByRole("button", { name: "follow" }));
    await waitFor(() =>
      expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: null } }),
    );
    expect(queryClient.getQueryData<{ locale: string | null }>(["settings", "read"])?.locale).toBeNull();
    expect(queryClient.getQueryData<{ locale: string | null }>(["settings"])?.locale).toBeNull();
  });

  it("a choice invents no row — entries that hold nothing stay empty", async () => {
    setUp = true;
    applyLocale("de");
    let held = false;
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings") {
        if (held) return new Promise(() => {});
        return { data: { locale: null, theme: null }, response: ok() };
      }
      throw new Error(`unexpected request: ${path}`);
    });
    render(
      <QueryClientProvider client={queryClient}>
        <SettingsProbe />
        <LanguageSwitcher variant="welcome" />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(queryClient.getQueryState(["settings"])?.status).toBe("success"));
    held = true;

    fireEvent.click(screen.getByRole("radio", { name: "English" }));
    await waitFor(() =>
      expect(api.PATCH).toHaveBeenCalledWith("/api/settings", { body: { locale: "en" } }),
    );
    // The strict entry never answered: the choice creates none — the
    // strict family holds real answers only.
    expect(queryClient.getQueryData(["settings", "read"])).toBeUndefined();
    // The tolerant entry carries no locale (the outage's dressed nulls
    // read exactly like a stored follow): nothing is set on it here —
    // the landed refetch is what reconciles it.
    expect(queryClient.getQueryData<{ locale: string | null }>(["settings"])?.locale).toBeNull();
    expect(queryClient.getQueryData<{ theme: string | null }>(["settings"])?.theme).toBeNull();
  });

  it("a refusal puts the moved entries back — the patch never outlives its write", async () => {
    setUp = true;
    storedLocale = "de";
    applyLocale("de");
    await renderSurfacesHeld(<LanguageSwitcher variant="welcome" />);
    api.PATCH.mockResolvedValueOnce({
      error: { detail: "refused" },
      response: new Response(null, { status: 503 }),
    });

    fireEvent.click(screen.getByRole("radio", { name: "English" }));
    await waitFor(() => expect(activeLocale()).toBe("de")); // the store restored
    expect(queryClient.getQueryData<{ locale: string | null }>(["settings", "read"])?.locale).toBe("de");
    expect(queryClient.getQueryData<{ locale: string | null }>(["settings"])?.locale).toBe("de");
  });

  it("a read already in flight cannot land its older answer over the choice", async () => {
    // #940: a read that started before the choice is cancelled at patch
    // time — its older answer's cache write is abandoned. The choice's
    // write hangs below, so the stale answer is landed exactly in the
    // window before the write commits (its invalidation would cancel the
    // read only after). Landing it must leave the pending choice standing
    // in both entries.
    setUp = true;
    storedLocale = "de";
    applyLocale("de");
    let held = false;
    let releaseStale: (() => void) | null = null;
    let releaseWrite: (() => void) | null = null;
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings") {
        if (held) {
          return new Promise<{ data: { locale: string | null; theme: string | null }; response: Response }>((resolve) => {
            releaseStale = () => resolve({ data: { locale: "de", theme: null }, response: ok() });
          });
        }
        return { data: { locale: storedLocale, theme: null }, response: ok() };
      }
      throw new Error(`unexpected request: ${path}`);
    });
    api.PATCH.mockImplementation(async (path: string, init?: { body?: { locale?: string | null } }) => {
      if (path !== "/api/settings") throw new Error(`unexpected request: ${path}`);
      return new Promise<{ data: { locale: string | null; theme: string | null }; response: Response }>((resolve) => {
        releaseWrite = () => {
          storedLocale = init?.body?.locale ?? null;
          resolve({ data: { locale: storedLocale, theme: null }, response: ok() });
        };
      });
    });
    render(
      <QueryClientProvider client={queryClient}>
        <SaveSurfaceProbe />
        <LanguageSwitcher variant="welcome" />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(queryClient.getQueryState(["settings", "read"])?.status).toBe("success"));
    await waitFor(() => expect(queryClient.getQueryState(["settings"])?.status).toBe("success"));
    held = true;

    // A settings read starts now and is in flight at choice moment.
    void queryClient.refetchQueries({ queryKey: ["settings"] });
    await waitFor(() => expect(releaseStale).not.toBeNull());

    fireEvent.click(screen.getByRole("radio", { name: "English" }));
    await waitFor(() =>
      expect(queryClient.getQueryData<{ locale: string | null }>(["settings", "read"])?.locale).toBe("en"),
    );

    await act(async () => {
      releaseStale?.(); // the older answer lands while the write is out
    });
    expect(queryClient.getQueryData<{ locale: string | null }>(["settings", "read"])?.locale).toBe("en");
    expect(queryClient.getQueryData<{ locale: string | null }>(["settings"])?.locale).toBe("en");

    // The write commits behind the window; its refetch answers the truth.
    await act(async () => {
      releaseWrite?.();
    });
    await waitFor(() => expect(storedLocale).toBe("en"));
  });

  it("a refused earlier choice never unwinds a newer choice — it stands", async () => {
    // #940's mirror variant: choice A (fr) hangs in flight, choice B (en)
    // is chosen and commits, then A's refusal arrives. A's snapshot is
    // obsolete the moment B patched — the restore must compare-and-swap
    // against the seam's last patch and leave B's value standing in the
    // caches, on the store, everywhere the choice wrote.
    setUp = true;
    storedLocale = "de";
    applyLocale("de");
    let held = false;
    let releaseFirstWrite: ((answer: { error: { detail: string }; response: Response }) => void) | null = null;
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings") {
        if (held) return new Promise(() => {});
        return { data: { locale: storedLocale, theme: null }, response: ok() };
      }
      throw new Error(`unexpected request: ${path}`);
    });
    api.PATCH.mockImplementation(async (path: string, init?: { body?: { locale?: string | null } }) => {
      if (path !== "/api/settings") throw new Error(`unexpected request: ${path}`);
      if (init?.body?.locale === "fr") {
        return new Promise<{ error: { detail: string }; response: Response }>((resolve) => {
          releaseFirstWrite = () => resolve({ error: { detail: "refused" }, response: new Response(null, { status: 503 }) });
        });
      }
      storedLocale = init?.body?.locale ?? null;
      return { data: { locale: storedLocale, theme: null }, response: ok() };
    });
    render(
      <QueryClientProvider client={queryClient}>
        <SaveSurfaceProbe />
        <NullChoiceProbe />
        <LanguageSwitcher variant="welcome" />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(queryClient.getQueryState(["settings", "read"])?.status).toBe("success"));
    await waitFor(() => expect(queryClient.getQueryState(["settings"])?.status).toBe("success"));
    held = true; // the writes' invalidation refetches never land

    // A: fr, its write hanging.
    fireEvent.click(screen.getByRole("button", { name: "fr" }));
    await waitFor(() =>
      expect(queryClient.getQueryData<{ locale: string | null }>(["settings", "read"])?.locale).toBe("fr"),
    );
    // B: en, chosen while A's write is still out — and it commits.
    fireEvent.click(screen.getByRole("radio", { name: "English" }));
    await waitFor(() =>
      expect(queryClient.getQueryData<{ locale: string | null }>(["settings", "read"])?.locale).toBe("en"),
    );

    // A's refusal lands now — B must stand everywhere.
    await act(async () => {
      releaseFirstWrite?.({ error: { detail: "refused" }, response: new Response(null, { status: 503 }) });
    });
    await waitFor(() => expect(api.PATCH).toHaveBeenCalledTimes(2));
    expect(queryClient.getQueryData<{ locale: string | null }>(["settings", "read"])?.locale).toBe("en");
    expect(queryClient.getQueryData<{ locale: string | null }>(["settings"])?.locale).toBe("en");
    expect(activeLocale()).toBe("en"); // the store keeps the newer choice too
  });
});
