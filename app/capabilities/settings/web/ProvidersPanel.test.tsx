// @vitest-environment jsdom
/**
 * The task list renders the server's effective rows, not a mirrored key list.
 * Each row names the profile that actually serves the task — the exact
 * assignment, a sibling's segment assignment or the default — and a task no
 * profile serves shows its environment kind. A key the frontend has never
 * heard of still renders (with the raw key as its label), which is the point
 * of the endpoint: the kernel's `KNOWN_TASK_KEYS` is the only list.
 *
 * The API client is mocked at its module boundary: the cases here are about
 * what the panel says, and the requests are verified by the backend and E2E
 * suites against the real stack.
 */
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@shell/lib/i18n";

vi.mock("@shell/lib/api/client", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(),
    PATCH: vi.fn(),
    PUT: vi.fn(),
    DELETE: vi.fn(),
  },
}));

import { client } from "@shell/lib/api/client";

import { ProvidersPanel } from "./ProvidersPanel";

/** The client's methods as plain mocks; the real client's generics stay out. */
const api = client as unknown as Record<
  "GET" | "POST" | "PATCH" | "PUT" | "DELETE",
  ReturnType<typeof vi.fn>
>;

const DEFAULT_PROFILE = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "Default",
  kind: "fake",
  base_url: null,
  model: "fake",
  api_key_mask: null,
  is_default: true,
  context_window: null,
  max_output_tokens: null,
  temperature: null,
  request_timeout: null,
  created_at: "2026-10-27T10:00:00Z",
  updated_at: "2026-10-27T10:00:00Z",
};

const SECOND_PROFILE = {
  ...DEFAULT_PROFILE,
  id: "22222222-2222-2222-2222-222222222222",
  name: "Second",
  is_default: false,
};

const TASKS = [
  {
    task_key: "writing.continuation",
    profile_id: DEFAULT_PROFILE.id,
    profile_name: "Default",
    kind: "fake",
    assignable: true,
  },
  {
    task_key: "chat.ask",
    profile_id: null,
    profile_name: null,
    kind: "openai-chat",
    assignable: true,
  },
  {
    task_key: "settings.test",
    profile_id: null,
    profile_name: null,
    kind: "audit",
    assignable: false,
  },
];

function ok(): Response {
  return new Response(null, { status: 200 });
}

async function renderPanel(): Promise<void> {
  render(<ProvidersPanel />);
  // The mount's fetch fills the list; the rows only exist after it lands.
  await screen.findByText(t("settings.task.writing.continuation"));
}

beforeEach(() => {
  api.GET.mockImplementation(async (path: string) => {
    switch (path) {
      case "/api/settings/profiles":
        return { data: [DEFAULT_PROFILE, SECOND_PROFILE], response: ok() };
      case "/api/settings/assignments":
        return { data: [], response: ok() };
      case "/api/settings/tasks":
        return { data: TASKS, response: ok() };
      default:
        throw new Error(`unexpected GET ${path}`);
    }
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("the task list", () => {
  it("names the profile that serves each task", async () => {
    await renderPanel();

    const viaDefault = t("settings.assignments.via", { profile: "Default" });
    expect(screen.getAllByText(viaDefault, { exact: false })).toHaveLength(1);
  });

  it("shows the environment kind when no profile serves", async () => {
    await renderPanel();

    const environment = t("settings.assignments.environment", {
      kind: t("settings.profiles.kind.openai-chat"),
    });
    expect(screen.getByText(environment)).toBeTruthy();
  });

  it("labels the audit-only key and offers it no assignment control", async () => {
    await renderPanel();

    // The server marks `settings.test` audit-only: the probe tests the clicked
    // profile, so the row must not claim an effective provider, must not offer
    // an assignment, and must not print the internal key.
    const label = t("settings.tasks.settings.test");
    expect(screen.getByText(label)).toBeTruthy();
    expect(screen.getByText(t("settings.profiles.taskAuditOnly"))).toBeTruthy();
    expect(screen.queryByLabelText(label)).toBeNull();
    expect(screen.queryByText(/settings\.test/)).toBeNull();
  });
});

describe("a secondary action whose request cannot be sent", () => {
  /** The panel's error surface, once the rejected fetch has been handled. */
  async function expectFailure(): Promise<void> {
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(t("settings.profiles.errorAction"));
  }

  it("names a test connection that never reaches the service", async () => {
    await renderPanel();
    api.POST.mockRejectedValue(new TypeError("Failed to fetch"));

    const [test] = screen.getAllByRole("button", {
      name: t("settings.profiles.test"),
    });
    await userEvent.click(test);

    await expectFailure();
  });

  it("names an assignment that never reaches the service", async () => {
    await renderPanel();
    api.PUT.mockRejectedValue(new TypeError("Failed to fetch"));

    await userEvent.selectOptions(
      screen.getByLabelText(t("settings.task.writing.continuation")),
      SECOND_PROFILE.id,
    );

    await expectFailure();
  });

  it("names a default flip that never reaches the service", async () => {
    await renderPanel();
    api.PATCH.mockRejectedValue(new TypeError("Failed to fetch"));

    await userEvent.click(
      screen.getByRole("button", { name: t("settings.profiles.makeDefault") }),
    );

    await expectFailure();
  });
});
