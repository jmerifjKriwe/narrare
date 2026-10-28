// @vitest-environment jsdom
/**
 * The demo picker on the first-run page: one card per bundled demo next to
 * the blank start, each naming the demo in its own language with its counts.
 * A blank selection sends no `demo` at all — the request the API always saw —
 * and picking a card sends that card's slug. The backend contract (which
 * slugs exist, what a demo load creates) is the backend suites'; the client
 * is mocked at its module boundary here.
 */
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@shell/lib/api/client", () => ({
  client: { POST: vi.fn() },
}));
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
}));

import { client } from "@shell/lib/api/client";
import { t } from "@shell/lib/i18n";

import { SetupPage } from "./SetupPage";

const api = client as unknown as { POST: ReturnType<typeof vi.fn> };

function postOk() {
  return { data: { novel_id: "11111111-1111-1111-1111-111111111111" }, response: new Response(null, { status: 201 }) };
}

async function typeTitleAndSubmit(): Promise<void> {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(t("setup.titleLabel")), "Ein Titel");
  await user.click(screen.getByRole("button", { name: t("setup.submit") }));
}

beforeEach(() => {
  api.POST.mockResolvedValue(postOk());
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("SetupPage", () => {
  it("renders the blank start and one card per demo", () => {
    render(<SetupPage />);
    expect(screen.getByText(t("setup.demo.blank"))).toBeTruthy();
    expect(screen.getByText("Im Stillen Wald")).toBeTruthy();
    expect(screen.getByText("Dead Signal")).toBeTruthy();
    expect(screen.getByText("Echoes of the Thornwall")).toBeTruthy();
    const subtitle = (language: string, chapters: number, entities: number): string =>
      `${t("setup.demo.language", { language })} · ${t("setup.demo.chapters", { count: chapters })} · ${t("setup.demo.entities", { count: entities })}`;
    expect(screen.getByText(subtitle("de", 2, 6))).toBeTruthy();
    expect(screen.getByText(subtitle("en", 3, 8))).toBeTruthy();
    expect(screen.getByText(subtitle("en", 4, 16))).toBeTruthy();
  });

  it("the blank selection sends no demo", async () => {
    render(<SetupPage />);
    await typeTitleAndSubmit();
    expect(api.POST).toHaveBeenCalledWith("/api/setup", {
      body: { novel_title: "Ein Titel" },
    });
    const body = api.POST.mock.calls[0][1].body as Record<string, unknown>;
    expect("demo" in body).toBe(false);
  });

  it("a demo selection sends the slug", async () => {
    render(<SetupPage />);
    const user = userEvent.setup();
    // the title goes in first: a selected demo parks the input
    await user.type(screen.getByLabelText(t("setup.titleLabel")), "Ein Titel");
    await user.click(screen.getByRole("radio", { name: /Dead Signal/ }));
    await user.click(screen.getByRole("button", { name: t("setup.submit") }));
    const body = api.POST.mock.calls[0][1].body as Record<string, unknown>;
    expect(body.demo).toBe("dead-signal");
    expect(body.novel_title).toBe("Ein Titel");
  });

  it("a selected demo disables the title input, names the demo's title, and keeps the typed title", async () => {
    render(<SetupPage />);
    const user = userEvent.setup();
    const title = (): HTMLInputElement =>
      screen.getByLabelText(t("setup.titleLabel")) as HTMLInputElement;
    await user.type(title(), "Mein Buch");
    await user.click(screen.getByRole("radio", { name: /Dead Signal/ }));
    // the demo names the novel — visibly, so nothing is silently dropped
    expect(title().disabled).toBe(true);
    expect(title().value).toBe("Mein Buch");
    expect(screen.getByText(t("setup.demo.titleReplaces", { title: "Dead Signal" }))).toBeTruthy();
    await user.click(
      screen.getByRole("radio", { name: new RegExp(t("setup.demo.blank")) }),
    );
    // back to blank: the input behaves exactly as before, text intact
    expect(title().disabled).toBe(false);
    expect(title().value).toBe("Mein Buch");
  });
});
