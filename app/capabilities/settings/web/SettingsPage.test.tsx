// @vitest-environment jsdom
/**
 * The Allgemein surface (W7 Task 3) — the settings capability's first web
 * surface, ported from the owner-approved harmonized `settings-allgemein-2`
 * draft onto the shell's tokens. Driven over a bare router with the API
 * client mocked at its module boundary; the queries, the locale store and
 * the theme store are real.
 *
 * The pins hold the four binding rulings: Sprache & Aussehen apply AT ONCE
 * through the existing seams (`useLanguageChoice`, the theme write — no
 * second mechanism, asserted on the wire), the profile form is ONE dirty
 * form whose save emits only dirtied fields with carried-null clears (the
 * novel-update rule on the wire), the section addresses the user-block menu
 * doors land on (`#profil-sektion`, `#tagesziel-feld`) focus their fields,
 * and the offline note answers with the draft's own card. Honest states
 * throughout: the loading skeleton, the outage with its retry, the empty
 * profile where the email answers as the label — not an error.
 */
import { QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { cleanup, configure, fireEvent, render, screen, waitFor, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import { client } from "@shell/lib/api/client";
import { catalogs, type Locale } from "@shell/lib/generated/catalogs";
import { t } from "@shell/lib/i18n";
import { applyLocale } from "@shell/lib/locale";
import { adoptServerTheme } from "@shell/lib/theme";
import { queryClient } from "@shell/lib/query";

import { SettingsPage } from "./SettingsPage";

const de = catalogs.de;
const en = catalogs.en;
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

configure({ asyncUtilTimeout: 5000 });

function ok(status = 200): Response {
  return new Response(null, { status });
}

/** The mock instance's row — the boot-adopted answers and the form's baseline. */
let settingsRow: {
  locale: Locale | null;
  theme: string | null;
  author_name: string | null;
  daily_goal_words: number | null;
  email: string | null;
};

/** The mock instance's driver kind — the backend's one-word truth for the
 *  card: `fake` while the fake adapter serves, `configured` once a
 *  provider does. */
let driverKind: "fake" | "configured";

function row(overrides: Partial<typeof settingsRow> = {}): typeof settingsRow {
  return {
    locale: "de",
    theme: "light",
    author_name: "H. Calder",
    daily_goal_words: 500,
    email: "h.calder@station7.de",
    ...overrides,
  };
}

function scriptApi() {
  api.GET.mockImplementation(async (path: string) => {
    if (path === "/api/settings") return { data: { ...settingsRow }, response: ok() };
    if (path === "/api/setup/status") return { data: { complete: true }, response: ok() };
    if (path === "/api/settings/driver") return { data: { kind: driverKind }, response: ok() };
    throw new Error(`unexpected request: ${path}`);
  });
  api.PATCH.mockImplementation(async (path: string, init?: { body?: Record<string, unknown> }) => {
    if (path === "/api/settings") {
      settingsRow = { ...settingsRow, ...(init?.body as Partial<typeof settingsRow>) };
      return { data: { ...settingsRow }, response: ok() };
    }
    if (path === "/api/settings/theme") {
      settingsRow = { ...settingsRow, theme: (init?.body?.theme as string | null) ?? null };
      return { data: { theme: settingsRow.theme }, response: ok() };
    }
    throw new Error(`unexpected request: ${path}`);
  });
}

/** The boot's adoption, as the shell root performs it: the store follows the
 *  row, so the immediate controls' faces are the row's truth. */
function adoptRow() {
  applyLocale(settingsRow.locale);
  adoptServerTheme(settingsRow.theme);
}

const testRoot = createRootRoute({ component: () => <Outlet /> });
const settingsRoute = createRoute({
  getParentRoute: () => testRoot,
  path: "/settings",
  component: SettingsPage,
});

function renderSettings(path = "/settings") {
  const router = createRouter({
    routeTree: testRoot.addChildren([settingsRoute]),
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

const settingsPatches = () => api.PATCH.mock.calls.filter(([path]) => path === "/api/settings");
const themePatches = () => api.PATCH.mock.calls.filter(([path]) => path === "/api/settings/theme");

function authorInput(): HTMLInputElement {
  return screen.getByLabelText(de["settings.author.label"]) as HTMLInputElement;
}

function goalInput(): HTMLInputElement {
  return screen.getByLabelText(de["settings.goal.label"]) as HTMLInputElement;
}

function saveButton(): HTMLButtonElement {
  return screen.getByRole("button", { name: de["settings.save"] }) as HTMLButtonElement;
}

function localeRadio(name: string): HTMLInputElement {
  return screen.getByRole("radio", { name }) as HTMLInputElement;
}

function themeRadio(name: string): HTMLInputElement {
  return screen.getByRole("radio", { name }) as HTMLInputElement;
}

beforeEach(() => {
  // Reset, not clear: a refusal test's scripted implementation must never
  // leak into the next case — clearAllMocks keeps implementations alive.
  api.GET.mockReset();
  api.PATCH.mockReset();
  settingsRow = row();
  driverKind = "fake";
  scriptApi();
  localStorage.clear();
  queryClient.clear();
  // The German visitor: the browser speaks de-DE.
  vi.stubGlobal("navigator", { language: "de-DE", languages: ["de-DE"] });
  // The boot's adoption, as the shell root performs it: the store follows
  // the row, so the immediate controls' faces are the row's truth.
  applyLocale(settingsRow.locale);
  adoptServerTheme(settingsRow.theme);
});

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
  applyLocale(null);
  adoptServerTheme(null);
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("the Allgemein surface — the draft's geometry", () => {
  it("renders the real fields from the row: name, goal, email hint, offline note", async () => {
    renderSettings();
    expect(await screen.findByLabelText(de["settings.author.label"])).toBeTruthy();
    expect(screen.getByRole("heading", { name: de["settings.appearance.heading"] })).toBeTruthy();
    expect(screen.getByRole("heading", { name: de["settings.profile.heading"] })).toBeTruthy();
    expect(authorInput().value).toBe("H. Calder");
    expect(goalInput().value).toBe("500");
    // The email answers as the fallback label — the hint names it.
    expect(screen.getByText(t("settings.author.hint.email", { email: "h.calder@station7.de" }))).toBeTruthy();
    // The offline note: the draft's card, title and body — it stands once
    // the driver read has answered the local fake driver for the instance.
    expect(await screen.findByText(de["settings.offline.title"])).toBeTruthy();
    expect(screen.getByText(de["settings.offline.body"])).toBeTruthy();
    expect(screen.getByText(de["settings.subtitle"])).toBeTruthy();
    expect(screen.getByText(de["settings.language.instant"])).toBeTruthy();
    expect(screen.getByText(de["settings.profile.saveNote"])).toBeTruthy();
  });

  it("the resolved language and theme mark their cards — the active faces", async () => {
    renderSettings();
    await screen.findByLabelText(de["settings.author.label"]);
    expect(localeRadio("Deutsch").checked).toBe(true);
    expect(localeRadio("English").checked).toBe(false);
    expect(themeRadio(de["settings.theme.light"]).checked).toBe(true);
    expect(themeRadio(de["settings.theme.dark"]).checked).toBe(false);
    expect(themeRadio(de["settings.theme.system"]).checked).toBe(false);
    // „Dem Browser folgen“ is the stored null — the row holds de, so off.
    expect(
      (screen.getByLabelText(de["settings.language.followBrowser"]) as HTMLInputElement).checked,
    ).toBe(false);
  });

  it("the loading state answers with the honest line while the ask stands", async () => {
    api.GET.mockImplementation(async () => new Promise<{ data?: unknown; response: Response }>(() => {}));
    renderSettings();
    expect(await screen.findByText(de["settings.loading"])).toBeTruthy();
    expect(screen.queryByLabelText(de["settings.author.label"])).toBeNull();
  });

  it("an outage names itself and the retry re-asks", async () => {
    let refuse = true;
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/setup/status") return { data: { complete: true }, response: ok() };
      if (refuse) throw new Error("offline");
      return { data: { ...settingsRow }, response: ok() };
    });
    renderSettings();
    expect(await screen.findByText(de["settings.loadFailed"])).toBeTruthy();
    // The flag flips BEFORE the click: the refetch's ask leaves on the
    // click dispatch, synchronously through the mock.
    refuse = false;
    fireEvent.click(screen.getByRole("button", { name: de["settings.retry"] }));
    expect(await screen.findByLabelText(de["settings.author.label"])).toBeTruthy();
  });

  it("the empty profile is no error: the neutral hint answers, the fields open empty", async () => {
    settingsRow = row({ author_name: null, daily_goal_words: null, email: null });
    renderSettings();
    await screen.findByLabelText(de["settings.author.label"]);
    expect(authorInput().value).toBe("");
    expect(goalInput().value).toBe("");
    expect(screen.getByText(de["settings.author.hint.neutral"])).toBeTruthy();
  });
});

describe("the immediate controls — the existing seams, no second mechanism", () => {
  it("a language choice applies at once and rides the language contract's one write", async () => {
    renderSettings();
    await screen.findByLabelText(de["settings.author.label"]);
    expect(settingsPatches().length).toBe(0);

    fireEvent.click(localeRadio("English"));
    // AT ONCE: the page re-renders in English before the answer lands.
    expect(await screen.findByRole("heading", { name: en["settings.heading"] })).toBeTruthy();
    await waitFor(() => expect(settingsPatches().length).toBe(1));
    expect(settingsPatches()[0][1].body).toEqual({ locale: "en" });
    // No second mechanism: the theme door is untouched by a language choice.
    expect(themePatches().length).toBe(0);
    expect(localeRadio("English").checked).toBe(true);
  });

  it("„Dem Browser folgen“ is the stored null — checking writes {locale: null} at once", async () => {
    settingsRow = row({ locale: null });
    adoptRow();
    renderSettings();
    await screen.findByLabelText(de["settings.author.label"]);
    const checkbox = screen.getByLabelText(de["settings.language.followBrowser"]) as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
    // The radio marks the RESOLVED language (the browser's de) while the
    // row holds no choice — the draft's own pairing.
    expect(localeRadio("Deutsch").checked).toBe(true);

    // Storing a choice ends the follow: the card writes the locale.
    fireEvent.click(localeRadio("English"));
    await waitFor(() => expect(settingsPatches()[0][1].body).toEqual({ locale: "en" }));
    await waitFor(() => expect(checkbox.checked).toBe(false));

    // Back to the browser: the checkbox writes the carried null.
    fireEvent.click(checkbox);
    await waitFor(() => expect(settingsPatches().length).toBe(2));
    expect(settingsPatches()[1][1].body).toEqual({ locale: null });
    await waitFor(() => expect(checkbox.checked).toBe(true));
    expect(localeRadio("Deutsch").checked).toBe(true);
  });

  it("a refused language choice restores the prior one — the contract's own honesty", async () => {
    api.PATCH.mockImplementation(async (path: string, init?: { body?: { locale?: string } }) => {
      if (path === "/api/settings" && init?.body?.locale === "en") {
        return { error: { detail: "refused" }, response: new Response(null, { status: 503 }) };
      }
      if (path === "/api/settings") {
        settingsRow = { ...settingsRow, ...(init?.body as Partial<typeof settingsRow>) };
        return { data: { ...settingsRow }, response: ok() };
      }
      throw new Error(`unexpected request: ${path}`);
    });
    renderSettings();
    await screen.findByLabelText(de["settings.author.label"]);

    fireEvent.click(localeRadio("English"));
    // The refusal restores — the heading returns to German.
    await waitFor(() => expect(screen.getByRole("heading", { name: de["settings.heading"] })).toBeTruthy());
    expect(localeRadio("Deutsch").checked).toBe(true);
  });

  it("a theme card applies at once and rides the theme write's one door", async () => {
    renderSettings();
    await screen.findByLabelText(de["settings.author.label"]);

    fireEvent.click(themeRadio(de["settings.theme.dark"]));
    expect(document.documentElement.dataset.theme).toBe("dark"); // at once
    await waitFor(() => expect(themePatches().length).toBe(1));
    expect(themePatches()[0][1].body).toEqual({ theme: "dark" });
    // The refreshed row marks the card — the write's own refetch.
    await waitFor(() => expect(themeRadio(de["settings.theme.dark"]).checked).toBe(true));

    fireEvent.click(themeRadio(de["settings.theme.system"]));
    await waitFor(() => expect(themePatches().length).toBe(2));
    expect(themePatches()[1][1].body).toEqual({ theme: null });
    expect(document.documentElement.dataset.theme).toBeUndefined();
    await waitFor(() => expect(themeRadio(de["settings.theme.system"]).checked).toBe(true));
    // One mechanism: a theme choice never touches the language door.
    expect(settingsPatches().length).toBe(0);
  });

  it("a refused theme choice restores the prior appearance", async () => {
    api.PATCH.mockImplementation(async (path: string, init?: { body?: { theme?: string | null } }) => {
      if (path === "/api/settings/theme" && init?.body?.theme === "dark") {
        return { error: { detail: "refused" }, response: new Response(null, { status: 503 }) };
      }
      throw new Error(`unexpected request: ${path}`);
    });
    renderSettings();
    await screen.findByLabelText(de["settings.author.label"]);

    fireEvent.click(themeRadio(de["settings.theme.dark"]));
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("light"));
    expect(themeRadio(de["settings.theme.light"]).checked).toBe(true);
  });
});

describe("the profile form — one dirty form", () => {
  async function open() {
    renderSettings();
    await screen.findByLabelText(de["settings.author.label"]);
  }

  it("a pristine save writes nothing — no diff, no ask", async () => {
    await open();
    fireEvent.click(saveButton());
    expect(settingsPatches().length).toBe(0);
  });

  it("a typed change shows the draft's dirty badge; Verwerfen returns the baseline", async () => {
    await open();
    expect(screen.queryByText(de["settings.profile.dirty"])).toBeNull();
    fireEvent.change(authorInput(), { target: { value: "Neuer Name" } });
    expect(screen.getByText(de["settings.profile.dirty"])).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: de["settings.discard"] }));
    expect(authorInput().value).toBe("H. Calder");
    expect(goalInput().value).toBe("500");
    expect(screen.queryByText(de["settings.profile.dirty"])).toBeNull();
    expect(settingsPatches().length).toBe(0);
  });

  it("the save emits only the dirtied field — absent keeps, on the wire", async () => {
    await open();
    fireEvent.change(authorInput(), { target: { value: "Neuer Name" } });
    fireEvent.click(saveButton());
    await waitFor(() => expect(settingsPatches().length).toBe(1));
    const body = settingsPatches()[0][1].body as Record<string, unknown>;
    expect(body).toEqual({ locale: "de", author_name: "Neuer Name" });
    expect("daily_goal_words" in body).toBe(false);
    // The saved truth stands in the fields; the badge retires.
    await waitFor(() => expect(authorInput().value).toBe("Neuer Name"));
    expect(screen.queryByText(de["settings.profile.dirty"])).toBeNull();
  });

  it("a carried null clears the name — the email keeps answering as the label", async () => {
    await open();
    const readsBefore = api.GET.mock.calls.filter(([path]) => path === "/api/settings").length;
    fireEvent.change(authorInput(), { target: { value: "" } });
    fireEvent.click(saveButton());
    await waitFor(() => expect(settingsPatches().length).toBe(1));
    expect(settingsPatches()[0][1].body).toEqual({ locale: "de", author_name: null });
    // The row answered the clear — and the email hint STILL stands: the
    // fallback label answers, no error and no invented name.
    await waitFor(() =>
      expect(api.GET.mock.calls.filter(([path]) => path === "/api/settings").length).toBeGreaterThan(
        readsBefore,
      ),
    );
    expect(
      screen.getByText(t("settings.author.hint.email", { email: "h.calder@station7.de" })),
    ).toBeTruthy();
  });

  it("a whitespace name is the honest unset — trimmed to the carried null", async () => {
    await open();
    fireEvent.change(authorInput(), { target: { value: "   " } });
    fireEvent.click(saveButton());
    await waitFor(() => expect(settingsPatches().length).toBe(1));
    expect(settingsPatches()[0][1].body).toEqual({ locale: "de", author_name: null });
  });

  it("the badge claims exactly what the wire would do — „0500“ is the stored 500", async () => {
    await open();
    // A zero-padded retyping parses to the stored value: no badge, and the
    // save is the same silent no-op the badge now claims.
    fireEvent.change(goalInput(), { target: { value: "0500" } });
    expect(screen.queryByText(de["settings.profile.dirty"])).toBeNull();
    fireEvent.click(saveButton());
    expect(settingsPatches().length).toBe(0);
    // A real change still shows it.
    fireEvent.change(goalInput(), { target: { value: "750" } });
    expect(screen.getByText(de["settings.profile.dirty"])).toBeTruthy();
    // And the trimmed name: a trailing space is the stored name, no badge.
    fireEvent.change(goalInput(), { target: { value: "500" } });
    fireEvent.change(authorInput(), { target: { value: "H. Calder " } });
    expect(screen.queryByText(de["settings.profile.dirty"])).toBeNull();
    // An unparseable field IS the dirty change it is — the save will
    // refuse it on the field, so the badge stands with it.
    fireEvent.change(authorInput(), { target: { value: "H. Calder" } });
    fireEvent.change(goalInput(), { target: { value: "abc" } });
    expect(screen.getByText(de["settings.profile.dirty"])).toBeTruthy();
  });

  it("the goal clears with a carried null and the name stays absent", async () => {
    await open();
    fireEvent.change(goalInput(), { target: { value: "" } });
    fireEvent.click(saveButton());
    await waitFor(() => expect(settingsPatches().length).toBe(1));
    const body = settingsPatches()[0][1].body as Record<string, unknown>;
    expect(body).toEqual({ locale: "de", daily_goal_words: null });
    expect("author_name" in body).toBe(false);
  });

  it("both fields dirtied ride together in one body", async () => {
    await open();
    fireEvent.change(authorInput(), { target: { value: "Maya Chen" } });
    fireEvent.change(goalInput(), { target: { value: "1.000" } });
    fireEvent.click(saveButton());
    await waitFor(() => expect(settingsPatches().length).toBe(1));
    expect(settingsPatches()[0][1].body).toEqual({
      locale: "de",
      author_name: "Maya Chen",
      daily_goal_words: 1000,
    });
    await waitFor(() => expect(goalInput().value).toBe("1.000"));
  });

  it("a reverted field is no change — only what still differs crosses", async () => {
    await open();
    fireEvent.change(authorInput(), { target: { value: "Neuer Name" } });
    fireEvent.change(authorInput(), { target: { value: "H. Calder" } });
    fireEvent.change(goalInput(), { target: { value: "750" } });
    fireEvent.click(saveButton());
    await waitFor(() => expect(settingsPatches().length).toBe(1));
    expect(settingsPatches()[0][1].body).toEqual({ locale: "de", daily_goal_words: 750 });
  });

  it("the save reads the row's freshest cache answer at click time — the language race", async () => {
    await open();
    // A language choice landed between the render and this save: the row's
    // refetch answered the cache, the form still wears the pre-switch row.
    // The save reads the cache at click time and carries the freshest known
    // locale — the choice set up here must survive this very save (#933).
    const cached = queryClient.getQueryData<{
      locale: string | null;
      theme: string | null;
      author_name: string | null;
      daily_goal_words: number | null;
      email: string | null;
    }>(["settings", "read"]);
    expect(cached?.locale).toBe("de");
    fireEvent.change(authorInput(), { target: { value: "Neuer Name" } });
    queryClient.setQueryData(["settings", "read"], { ...cached, locale: "en" });
    fireEvent.click(saveButton());
    await waitFor(() => expect(settingsPatches().length).toBe(1));
    expect(settingsPatches()[0][1].body).toEqual({ locale: "en", author_name: "Neuer Name" });
  });

  it("a save right after a language choice carries the chosen locale — the in-flight window", async () => {
    // #939, the window a landed cache answer cannot close: the choice
    // applies at once, PATCHes, and only the landed refetch moves the
    // settings caches. While that refetch stands in flight the cached row
    // still wears the pre-switch answer, and a save in exactly this window
    // used to send it back — reverting the choice if it committed later.
    // The choice itself must move the caches at choice time, so the save's
    // click-time read sees the pending choice.
    let reads = 0;
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings") {
        reads += 1;
        // The page's two reads answer; everything after — the choice's
        // invalidation refetch — never lands. The window stays open.
        if (reads > 2) return new Promise(() => {});
        return { data: { ...settingsRow }, response: ok() };
      }
      if (path === "/api/setup/status") return { data: { complete: true }, response: ok() };
      if (path === "/api/settings/driver") return { data: { kind: driverKind }, response: ok() };
      throw new Error(`unexpected request: ${path}`);
    });
    await open();

    fireEvent.click(localeRadio("English"));
    await waitFor(() => expect(settingsPatches().length).toBe(1));
    expect(settingsPatches()[0][1].body).toEqual({ locale: "en" });

    // The page speaks the choice at once; the form's typed answer stands.
    fireEvent.change(screen.getByLabelText(en["settings.author.label"]), {
      target: { value: "Neuer Name" },
    });
    fireEvent.click(screen.getByRole("button", { name: en["settings.save"] }));
    await waitFor(() => expect(settingsPatches().length).toBe(2));
    expect(settingsPatches()[1][1].body).toEqual({ locale: "en", author_name: "Neuer Name" });
  });

  it("a settings read already in flight cannot land its older answer over the choice", async () => {
    // #940: a read that STARTED before the choice — another write's
    // invalidation refetch, a stale-expired remount — lands after the
    // optimistic patch and used to replace the pending choice with
    // pre-choice truth; a save in that window carried the stale locale.
    // The choice cancels the reads in flight before it patches, so the
    // older answer's write is abandoned: landing it below must change
    // nothing, and the save still carries the chosen locale.
    let reads = 0;
    let releaseStale: (() => void) | null = null;
    let releaseChoiceWrite: (() => void) | null = null;
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings") {
        reads += 1;
        // The page's two reads answer; the third — the refetch started
        // below, already in flight at choice moment — hangs until the
        // test lands its stale answer.
        if (reads === 3) {
          const frozen = { ...settingsRow, locale: "de" as const };
          return new Promise<{ data: typeof frozen; response: Response }>((resolve) => {
            releaseStale = () => resolve({ data: frozen, response: ok() });
          });
        }
        return { data: { ...settingsRow }, response: ok() };
      }
      if (path === "/api/setup/status") return { data: { complete: true }, response: ok() };
      if (path === "/api/settings/driver") return { data: { kind: driverKind }, response: ok() };
      throw new Error(`unexpected request: ${path}`);
    });
    api.PATCH.mockImplementation(async (path: string, init?: { body?: Record<string, unknown> }) => {
      if (path === "/api/settings") {
        const body = init?.body as Partial<typeof settingsRow> | undefined;
        // The choice's write hangs — the flagged window is exactly the
        // span before this write commits. The profile save (its body
        // names a field beside the locale) answers normally.
        if (body !== undefined && !("author_name" in body) && !("daily_goal_words" in body)) {
          return new Promise<{ data: typeof settingsRow; response: Response }>((resolve) => {
            releaseChoiceWrite = () => {
              const written = { ...settingsRow, locale: body.locale ?? null };
              resolve({ data: written, response: ok() });
            };
          });
        }
        settingsRow = { ...settingsRow, ...(body as Partial<typeof settingsRow>) };
        return { data: { ...settingsRow }, response: ok() };
      }
      if (path === "/api/settings/theme") {
        settingsRow = { ...settingsRow, theme: (init?.body?.theme as string | null) ?? null };
        return { data: { theme: settingsRow.theme }, response: ok() };
      }
      throw new Error(`unexpected request: ${path}`);
    });
    await open();

    // A settings read starts now and is in flight at choice moment.
    void queryClient.refetchQueries({ queryKey: ["settings"] });
    await waitFor(() => expect(releaseStale).not.toBeNull());

    fireEvent.click(localeRadio("English"));
    await waitFor(() =>
      expect(queryClient.getQueryData<{ locale: string | null }>(["settings", "read"])?.locale).toBe("en"),
    );

    // The older answer lands while the choice's write is still out —
    // exactly the window before the write's own invalidation would
    // cancel it. It must not stick.
    await act(async () => {
      releaseStale?.();
    });
    expect(queryClient.getQueryData<{ locale: string | null }>(["settings", "read"])?.locale).toBe("en");

    // The page speaks the choice; the save carries it, not the stale read.
    fireEvent.change(screen.getByLabelText(en["settings.author.label"]), {
      target: { value: "Neuer Name" },
    });
    fireEvent.click(screen.getByRole("button", { name: en["settings.save"] }));
    await waitFor(() => expect(settingsPatches().length).toBe(2));
    expect(settingsPatches()[1][1].body).toEqual({ locale: "en", author_name: "Neuer Name" });

    // The choice's write commits behind the save; its refetch follows.
    await act(async () => {
      releaseChoiceWrite?.();
    });
    await waitFor(() => expect(settingsRow.locale).toBe("en"));
  });

  it("an out-of-bounds goal answers on its field and writes nothing", async () => {
    await open();
    fireEvent.change(authorInput(), { target: { value: "Neuer Name" } });
    fireEvent.change(goalInput(), { target: { value: "0" } });
    fireEvent.click(saveButton());
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText(de["settings.goal.invalid"])).toBeTruthy();
    expect(settingsPatches().length).toBe(0);

    fireEvent.change(goalInput(), { target: { value: "abc" } });
    fireEvent.click(saveButton());
    expect(screen.getByText(de["settings.goal.invalid"])).toBeTruthy();
    expect(settingsPatches().length).toBe(0);
  });

  it("the busy face holds the buttons while the write runs", async () => {
    // The executor assignment runs synchronously; a non-null holder keeps
    // TS's narrowing out of the way.
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    api.PATCH.mockImplementationOnce(async () => {
      await gate;
      return { data: { ...settingsRow }, response: ok() };
    });
    await open();
    fireEvent.change(authorInput(), { target: { value: "Neuer Name" } });
    fireEvent.click(saveButton());
    // While the write runs, the save button speaks the busy face and the
    // two buttons rest — no second click, no discard mid-flight.
    const busy = await screen.findByRole("button", { name: de["settings.saving"] });
    expect((busy as HTMLButtonElement).disabled).toBe(true);
    expect(
      (screen.getByRole("button", { name: de["settings.discard"] }) as HTMLButtonElement).disabled,
    ).toBe(true);

    release();
    await waitFor(() =>
      expect(
        (screen.getByRole("button", { name: de["settings.save"] }) as HTMLButtonElement).disabled,
      ).toBe(false),
    );
    expect(screen.queryByText(de["settings.saving"])).toBeNull();
  });

  it("a 422 refusal names itself, keeps the answers, and the retry re-runs the ask", async () => {
    let refuse = true;
    api.PATCH.mockImplementation(async (path: string) => {
      if (path !== "/api/settings") throw new Error(`unexpected request: ${path}`);
      if (refuse) {
        return {
          error: { detail: [{ loc: ["body", "daily_goal_words"], msg: "out of bounds" }] },
          response: new Response(null, { status: 422 }),
        };
      }
      settingsRow = { ...settingsRow, author_name: "Neuer Name" };
      return { data: { ...settingsRow }, response: ok() };
    });
    await open();
    fireEvent.change(authorInput(), { target: { value: "Neuer Name" } });
    fireEvent.click(saveButton());
    expect(await screen.findByText(de["settings.refused"])).toBeTruthy();
    // The answers stay in the fields — a refusal never eats the writer's work.
    expect(authorInput().value).toBe("Neuer Name");

    refuse = false;
    fireEvent.click(screen.getByRole("button", { name: de["settings.retry"] }));
    await waitFor(() => expect(screen.queryByText(de["settings.refused"])).toBeNull());
    await waitFor(() => expect(screen.queryByText(de["settings.profile.dirty"])).toBeNull());
    expect(authorInput().value).toBe("Neuer Name");
  });

  it("any other refusal wears the family's loss-free line", async () => {
    api.PATCH.mockResolvedValueOnce({
      data: undefined,
      response: new Response(null, { status: 500 }),
    });
    await open();
    fireEvent.change(authorInput(), { target: { value: "Neuer Name" } });
    fireEvent.click(saveButton());
    expect(await screen.findByText(de["settings.error"])).toBeTruthy();
    expect(authorInput().value).toBe("Neuer Name");
  });
});

describe("the offline card — the driver read's word, not a printed claim", () => {
  it("stands while the driver read answers the local fake driver", async () => {
    renderSettings();
    await screen.findByLabelText(de["settings.author.label"]);
    expect(await screen.findByText(de["settings.offline.title"])).toBeTruthy();
    expect(screen.getByText(de["settings.offline.body"])).toBeTruthy();
  });

  it("hides once the driver read names a configured instance", async () => {
    driverKind = "configured";
    renderSettings();
    await screen.findByLabelText(de["settings.author.label"]);
    // Let the driver read settle, then assert the absence.
    await waitFor(() => expect(api.GET.mock.calls.filter(([path]) => path === "/api/settings/driver").length).toBeGreaterThan(0));
    expect(screen.queryByText(de["settings.offline.title"])).toBeNull();
  });

  it("no answer, no claim — a failed driver read hides the card", async () => {
    api.GET.mockImplementation(async (path: string) => {
      if (path === "/api/settings/driver") {
        return { data: undefined, response: new Response(null, { status: 500 }) };
      }
      if (path === "/api/settings") return { data: { ...settingsRow }, response: ok() };
      throw new Error(`unexpected request: ${path}`);
    });
    renderSettings();
    await screen.findByLabelText(de["settings.author.label"]);
    await waitFor(() => expect(api.GET.mock.calls.filter(([path]) => path === "/api/settings/driver").length).toBeGreaterThan(0));
    expect(screen.queryByText(de["settings.offline.title"])).toBeNull();
  });
});

describe("the section addresses — the menu's real doors", () => {
  it("#tagesziel-feld deep-links to the goal field's focus", async () => {
    renderSettings("/settings#tagesziel-feld");
    await screen.findByLabelText(de["settings.author.label"]);
    await waitFor(() => expect(document.activeElement).toBe(goalInput()));
  });

  it("#profil-sektion deep-links to the author field's focus", async () => {
    renderSettings("/settings#profil-sektion");
    await screen.findByLabelText(de["settings.author.label"]);
    await waitFor(() => expect(document.activeElement).toBe(authorInput()));
  });

  it("a same-page door navigation moves the focus — the menu while the page stands", async () => {
    const router = renderSettings("/settings");
    await screen.findByLabelText(de["settings.author.label"]);
    expect(document.activeElement).not.toBe(goalInput());

    await router.navigate({ to: "/settings", hash: "tagesziel-feld" });
    await waitFor(() => expect(document.activeElement).toBe(goalInput()));

    await router.navigate({ to: "/settings", hash: "profil-sektion" });
    await waitFor(() => expect(document.activeElement).toBe(authorInput()));
  });
});

describe("du-tone — the catalogs speak to the writer", () => {
  it("de duzt, fr tutoie — the three catalogs carry the same keys", () => {
    expect(de["settings.subtitle"]).toContain("deine");
    expect(catalogs.fr["settings.subtitle"]).toMatch(/\btes\b/);
    expect(en["settings.subtitle"]).toContain("your");
    expect(Object.keys(catalogs.de).filter((key) => key.startsWith("settings.")).sort()).toEqual(
      Object.keys(catalogs.fr).filter((key) => key.startsWith("settings.")).sort(),
    );
  });
});
