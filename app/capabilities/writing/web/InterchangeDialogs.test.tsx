// @vitest-environment jsdom
/**
 * The shelf's interchange dialogs, spoken by the catalog: the export dialog
 * proposes a timestamped path (`<slug>-<yyyymmdd-hhmm>`) and submits the
 * chosen mode, a path export answers with a receipt the dialog shows —
 * counts and path, nothing silent — a ZIP export never answers with one
 * (the archive goes to the browser as a blob download through a temporary
 * anchor, the dialog closes), and the import dialog uploads the one source
 * it was given (file or path — never both), targets a new or an existing
 * novel, and renders the report: every count class, every conflict as a
 * `file — reason` row, every metadata field — all of it text nodes, so an
 * archive-supplied name can never become markup.
 */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Novel } from "@shell/lib/api/client";
import { t } from "@shell/lib/i18n";

import { ExportNovelDialog, ImportArchiveDialog } from "./InterchangeDialogs";
import { proposeExportPath } from "./interchange";

/**
 * The typed client captures `globalThis.Request` AND `globalThis.fetch`
 * when its module loads — before any test hook runs. Both are patched in
 * a hoisted block, before that import chain runs: the Request resolves
 * the app's relative paths (`baseUrl: ""`) against a stand-in origin —
 * paths, methods and bodies untouched, only the origin the test never
 * looks at changes — and records every request body it was handed, so
 * the mock reads the FormData the dialog actually built (undici's own
 * re-parsing chokes on the jsdom File realm and answers empty). The
 * fetch global is a delegator the per-test mock plugs into. Direct
 * assignment, so `unstubAllGlobals` (the URL/anchor restore) leaves
 * them alone.
 */
const { setFetchMock, sentBodies } = vi.hoisted(() => {
  const sentBodies: unknown[] = [];
  class RelativeRequest extends globalThis.Request {
    constructor(input: RequestInfo | URL, init?: RequestInit) {
      if (init !== undefined && "body" in init) sentBodies.push(init.body);
      super(new URL(String(input), "http://interchange.test").href, init);
    }
  }
  const globals = globalThis as unknown as {
    Request: unknown;
    fetch: unknown;
  };
  globals.Request = RelativeRequest;
  let current: (
    input: RequestInfo | URL,
    init?: RequestInit,
  ) => Promise<Response> = async () => {
    throw new Error("no scripted fetch installed");
  };
  const delegator = ((input: RequestInfo | URL, init?: RequestInit) =>
    current(input, init)) as typeof fetch;
  globals.fetch = delegator;
  return {
    sentBodies,
    setFetchMock: (mock: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>) => {
      current = mock;
    },
  };
});

const NOVEL: Novel = {
  id: "2f0b8a52-9d3e-4f6e-8df5-7db9df0f4a51",
  title: "Dead Signal",
  author: null,
  blurb: null,
  created_at: "2026-10-28T10:00:00Z",
  genre: null,
  language: null,
  updated_at: "2026-10-28T10:00:00Z",
};

const TARGET: Novel = {
  ...NOVEL,
  id: "a6f4c6d1-2f3e-4a5b-8c9d-0e1f2a3b4c5d",
  title: "Im Stillen Wald",
};

/**
 * What went over the wire, as the endpoint receives it: URL, method and
 * the body exactly as the dialog handed it over. Scripted answers are
 * shifted in order; a click without a scripted answer fails instead of
 * hanging on undefined.
 */
type Wire = { url: string; method: string; json: unknown; form: FormData | null };
let wire: Wire[] = [];
let answers: unknown[] = [];

function jsonResponse(status: number, body: unknown): unknown {
  const payload = JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
    // The typed client reads answers through `text()` (then parses), so
    // the stub speaks both doors.
    text: async () => payload,
  };
}

function zipResponse(filename: string): unknown {
  return {
    ok: true,
    status: 200,
    headers: new Headers({
      "content-type": "application/zip",
      "content-disposition": `attachment; filename="${filename}"`,
    }),
    blob: async () => new Blob(["PK"], { type: "application/zip" }),
    text: async () => "PK",
  };
}

const fetchMock = vi.fn(async (input: Request | string | URL, init?: RequestInit) => {
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
  const method =
    typeof input === "string" || input instanceof URL
      ? (init?.method ?? "GET")
      : input.method;
  // The body as it was handed over: the FormData the dialog built, or the
  // JSON string — read directly, no body-consuming probes. The typed
  // client's body is recorded at Request construction; the raw export
  // call hands its body in `init`.
  const sent = typeof input === "string" ? init?.body : sentBodies.shift();
  let json: unknown = undefined;
  let form: FormData | null = null;
  if (sent instanceof FormData) form = sent;
  else if (typeof sent === "string") {
    try {
      json = JSON.parse(sent);
    } catch {
      // a non-JSON string body: recorded as neither
    }
  }
  wire.push({ url, method, json, form });
  const answer = answers.shift();
  expect(answer, "every click is scripted").toBeDefined();
  return answer as Response;
});

/** The blob download seam, as the browser has it: jsdom has no
 * `createObjectURL`, and an anchor `click` would navigate. Both are
 * captured — the anchor's href and download name are the receipt. */
let objectUrls: string[] = [];
let revokedUrls: string[] = [];
let anchorClicks: { href: string; download: string }[] = [];
let savedUrlStatics: { create?: PropertyDescriptor; revoke?: PropertyDescriptor } = {};
let savedAnchorClick: (() => void) | undefined;

function captureDownloadSeam(): void {
  const urlStatics = globalThis.URL as unknown as Record<string, PropertyDescriptor | undefined>;
  savedUrlStatics = {
    create: Object.getOwnPropertyDescriptor(urlStatics, "createObjectURL"),
    revoke: Object.getOwnPropertyDescriptor(urlStatics, "revokeObjectURL"),
  };
  Object.defineProperty(globalThis.URL, "createObjectURL", {
    value: vi.fn(() => {
      const url = `blob:test-${objectUrls.length}`;
      objectUrls.push(url);
      return url;
    }),
    configurable: true,
  });
  Object.defineProperty(globalThis.URL, "revokeObjectURL", {
    value: vi.fn((url: string) => {
      revokedUrls.push(url);
    }),
    configurable: true,
  });
  savedAnchorClick = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function (this: HTMLAnchorElement) {
    anchorClicks.push({ href: this.href, download: this.download });
  };
}

beforeEach(() => {
  wire = [];
  answers = [];
  objectUrls = [];
  revokedUrls = [];
  anchorClicks = [];
  savedUrlStatics = {};
  savedAnchorClick = undefined;
  setFetchMock(fetchMock);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  const urlStatics = globalThis.URL as unknown as Record<string, PropertyDescriptor | undefined>;
  for (const [key, descriptor] of [
    ["createObjectURL", savedUrlStatics.create],
    ["revokeObjectURL", savedUrlStatics.revoke],
  ] as const) {
    if (descriptor) Object.defineProperty(globalThis.URL, key, descriptor);
    else delete urlStatics[key];
  }
  if (savedAnchorClick) HTMLAnchorElement.prototype.click = savedAnchorClick;
});

describe("the export dialog", () => {
  it("proposes a timestamped path and submits the mode", async () => {
    // The proposal's exact shape, pinned as a pure function: the title's
    // slug, the stamp `<yyyymmdd>-<hhmm>` — the common path that never
    // hits the non-empty refusal (D10).
    expect(proposeExportPath("Im Stillen Wald", new Date(2026, 0, 2, 3, 4))).toBe(
      "im-stillen-wald-20260102-0304",
    );
    expect(proposeExportPath("Dead Signal", new Date(2026, 9, 28, 14, 5))).toBe(
      "dead-signal-20261028-1405",
    );

    answers.push(jsonResponse(200, { path: "/home/me/dead-signal", chapters: 3, entities: 7 }));
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    render(<ExportNovelDialog novel={NOVEL} />);

    await user.click(screen.getByRole("button", { name: t("shelf.export") }));
    const pathField = (await screen.findByLabelText(t("shelf.export.pathLabel"))) as HTMLInputElement;
    expect(pathField.value).toMatch(/^dead-signal-\d{8}-\d{4}$/);

    await user.click(screen.getByRole("button", { name: t("shelf.export.submit") }));

    // The path mode went out as the path mode: the chosen mode in the body,
    // the proposal as the path.
    await waitFor(() => expect(wire).toHaveLength(1));
    expect(wire[0]!.url).toContain(`/api/writing/novels/${NOVEL.id}/export`);
    expect(wire[0]!.method).toBe("POST");
    expect(wire[0]!.json).toEqual({ mode: "path", path: pathField.value });

    // The receipt, not silence: where it went and how much.
    expect(await screen.findByText(t("shelf.export.doneHeading"))).toBeTruthy();
    expect(screen.getByText(t("shelf.export.donePath", { path: "/home/me/dead-signal" }))).toBeTruthy();
    expect(screen.getByText(t("shelf.export.doneChapters", { count: 3 }))).toBeTruthy();
    expect(screen.getByText(t("shelf.export.doneEntities", { count: 7 }))).toBeTruthy();
  });

  it("delegates the ZIP to the browser — blob, anchor, revoke, no receipt", async () => {
    captureDownloadSeam();
    answers.push(zipResponse("dead-signal.zip"));
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    render(<ExportNovelDialog novel={NOVEL} />);

    await user.click(screen.getByRole("button", { name: t("shelf.export") }));
    await screen.findByLabelText(t("shelf.export.pathLabel"));
    await user.click(screen.getByRole("radio", { name: t("shelf.export.modeZip") }));
    // The path question belongs to the path mode only; the ZIP needs no
    // folder, so the field (and a stale proposal with it) steps aside.
    expect(screen.queryByLabelText(t("shelf.export.pathLabel"))).toBeNull();

    await user.click(screen.getByRole("button", { name: t("shelf.export.submit") }));

    // The wire carries the mode alone — no path key to half-mean.
    await waitFor(() => expect(wire).toHaveLength(1));
    expect(wire[0]!.json).toEqual({ mode: "zip" });

    // The browser got the bytes: one object URL, one anchor click named
    // after the Content-Disposition, one revoke — the temporary anchor
    // leaves nothing behind.
    await waitFor(() => expect(anchorClicks).toHaveLength(1));
    expect(anchorClicks[0]!.download).toBe("dead-signal.zip");
    expect(anchorClicks[0]!.href).toBe(objectUrls[0]);
    expect(revokedUrls).toEqual(objectUrls);
    const downloaded = (URL.createObjectURL as ReturnType<typeof vi.fn>).mock.calls[0]?.[0];
    expect(downloaded).toBeInstanceOf(Blob);

    // No dialog report: the dialog is gone and no receipt is on the page.
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.body.textContent).not.toContain(t("shelf.export.doneHeading"));
  });

  it("names a non-empty target instead of a generic failure", async () => {
    answers.push(
      jsonResponse(409, { detail: { code: "target_not_empty", path: "/home/me/full" } }),
    );
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    render(<ExportNovelDialog novel={NOVEL} />);

    await user.click(screen.getByRole("button", { name: t("shelf.export") }));
    await screen.findByLabelText(t("shelf.export.pathLabel"));
    await user.click(screen.getByRole("button", { name: t("shelf.export.submit") }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe(
      t("shelf.export.targetNotEmpty", { path: "/home/me/full" }),
    );
    // The refusal is not the end of the form: the proposal is still there
    // to be corrected, and the dialog never claimed an export happened.
    expect(screen.queryByText(t("shelf.export.doneHeading"))).toBeNull();
  });
});

describe("the import dialog", () => {
  it("shows the report with conflicts", async () => {
    const hostileFile = "chapters/03-<script>alert(1)</script>.md";
    answers.push(
      jsonResponse(201, {
        novel_id: TARGET.id,
        chapters_new: 2,
        chapters_revised: 1,
        chapters_already_current: 4,
        entities_new: 3,
        entities_revised: 0,
        entities_renamed: 2,
        entities_already_current: 5,
        relations_created: 6,
        relations_already_current: 1,
        conflicts: [{ file: hostileFile, reason: "unreadable frontmatter" }],
        metadata_conflicts: ["genre", "language"],
      }),
    );
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    render(<ImportArchiveDialog novels={[NOVEL, TARGET]} />);

    await user.click(screen.getByRole("button", { name: t("shelf.import") }));
    // The source is the path here: the file input stays empty, the path
    // field decides. Exactly one of the two reaches the wire.
    await user.type(await screen.findByLabelText(t("shelf.import.pathLabel")), "/tmp/archives/dead-signal.zip");
    // The target defaults to a new novel; the import goes out under that.
    await user.click(screen.getByRole("button", { name: t("shelf.import.submit") }));

    await waitFor(() => expect(wire).toHaveLength(1));
    expect(wire[0]!.url).toContain("/api/writing/novels/import");
    expect(wire[0]!.method).toBe("POST");
    expect(wire[0]!.form?.get("path")).toBe("/tmp/archives/dead-signal.zip");
    expect(wire[0]!.form?.has("archive")).toBe(false);
    expect(wire[0]!.form?.has("novel_id")).toBe(false);

    // Every class the report carries is on the page — the zeros included:
    // nothing the engine counted may go silent.
    expect(await screen.findByText(t("shelf.report.heading"))).toBeTruthy();
    expect(screen.getByText(t("shelf.report.chaptersNew", { count: 2 }))).toBeTruthy();
    expect(screen.getByText(t("shelf.report.chaptersRevised", { count: 1 }))).toBeTruthy();
    expect(screen.getByText(t("shelf.report.chaptersUnchanged", { count: 4 }))).toBeTruthy();
    expect(screen.getByText(t("shelf.report.entitiesNew", { count: 3 }))).toBeTruthy();
    expect(screen.getByText(t("shelf.report.entitiesRevised", { count: 0 }))).toBeTruthy();
    expect(screen.getByText(t("shelf.report.entitiesRenamed", { count: 2 }))).toBeTruthy();
    expect(screen.getByText(t("shelf.report.entitiesUnchanged", { count: 5 }))).toBeTruthy();
    expect(screen.getByText(t("shelf.report.relationsCreated", { count: 6 }))).toBeTruthy();
    expect(screen.getByText(t("shelf.report.relationsUnchanged", { count: 1 }))).toBeTruthy();

    // The conflict as a `file — reason` row — as a text node: the
    // archive-supplied name rides the catalog formatter, never markup.
    expect(
      screen.getByText(t("shelf.report.conflictRow", {
        file: hostileFile,
        reason: "unreadable frontmatter",
      })),
    ).toBeTruthy();
    expect(document.body.innerHTML).not.toContain("<script");
    expect(document.querySelectorAll("script")).toHaveLength(0);

    // The metadata fields the merge refused to touch, named one by one.
    expect(screen.getByText(t("shelf.report.metadataHeading", { count: 2 }))).toBeTruthy();
    expect(screen.getByText("genre")).toBeTruthy();
    expect(screen.getByText("language")).toBeTruthy();
  });

  it("uploads a file into an existing novel — and refuses both sources at once", async () => {
    answers.push(
      jsonResponse(201, {
        novel_id: TARGET.id,
        chapters_new: 0,
        chapters_revised: 0,
        chapters_already_current: 0,
        entities_new: 0,
        entities_revised: 0,
        entities_renamed: 0,
        entities_already_current: 0,
        relations_created: 0,
        relations_already_current: 0,
        conflicts: [],
        metadata_conflicts: [],
      }),
    );
    const user = userEvent.setup({ pointerEventsCheck: 0 });
    render(<ImportArchiveDialog novels={[TARGET]} />);

    await user.click(screen.getByRole("button", { name: t("shelf.import") }));
    const fileInput = await screen.findByLabelText(t("shelf.import.fileLabel"));
    await user.upload(fileInput, new File(["PK"], "dead-signal.zip", { type: "application/zip" }));

    // The dialog owns the exact-one rule before the wire does: a typed
    // path beside the chosen file is refused by name, and nothing is sent.
    await user.type(await screen.findByLabelText(t("shelf.import.pathLabel")), "/tmp/also-this.zip");
    await user.click(screen.getByRole("button", { name: t("shelf.import.submit") }));

    expect(screen.getByRole("alert").textContent).toBe(t("shelf.import.bothSources"));
    expect(wire).toHaveLength(0);

    // The path text cleared, the file stays the one source; the target is
    // an existing novel picked from the shelf's own list.
    await user.clear(await screen.findByLabelText(t("shelf.import.pathLabel")));
    await user.click(screen.getByRole("radio", { name: t("shelf.import.targetExisting") }));
    const select = (await screen.findByLabelText(t("shelf.import.targetNovelLabel"))) as HTMLSelectElement;
    await user.selectOptions(select, TARGET.id);
    await user.click(screen.getByRole("button", { name: t("shelf.import.submit") }));

    await waitFor(() => expect(wire).toHaveLength(1));
    expect(wire[0]!.form?.get("novel_id")).toBe(TARGET.id);
    const archive = wire[0]!.form?.get("archive");
    expect(archive).toBeInstanceOf(File);
    expect((archive as File).name).toBe("dead-signal.zip");
    expect(wire[0]!.form?.has("path")).toBe(false);

    // The empty report is still a report: the heading says what happened,
    // and the absent rows say why nothing else is listed.
    expect(await screen.findByText(t("shelf.report.heading"))).toBeTruthy();
    expect(screen.getByText(t("shelf.report.chaptersNew", { count: 0 }))).toBeTruthy();
    expect(screen.queryByText(t("shelf.report.conflictsHeading", { count: 1 }))).toBeNull();
    expect(screen.queryByText(t("shelf.report.metadataHeading", { count: 1 }))).toBeNull();
  });
});
