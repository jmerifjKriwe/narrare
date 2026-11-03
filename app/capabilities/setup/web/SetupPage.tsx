import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { client } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { Button } from "@shell/ui/Button";
import { Cover } from "@shell/ui/Cover";
import { Field, Input } from "@shell/ui/field";
import { Notice } from "@shell/ui/Notice";
import { Panel } from "@shell/ui/Panel";

/**
 * The demo corpus as the picker shows it, mirroring the kernel manifest
 * (`app/kernel/interchange/demos.py`, same order, same slugs): the demos are
 * content in their own language, so their titles are not catalog keys — only
 * the labels around them are. The counts are the bundled archives' facts;
 * the setup suite's `test_demo_manifest.py` cross-checks both manifests
 * against each other and against the parsed archives, so a demo added on
 * one side only — or a card with a wrong count — is a red test.
 */
const DEMOS = [
  { slug: "im-stillen-wald", title: "Im Stillen Wald", language: "de", chapters: 2, entities: 6 },
  { slug: "dead-signal", title: "Dead Signal", language: "en", chapters: 3, entities: 8 },
  {
    slug: "echoes-of-the-thornwall",
    title: "Echoes of the Thornwall",
    language: "en",
    chapters: 4,
    entities: 16,
  },
] as const;

/**
 * The setup page: start blank or from a demo, then straight into the editor.
 * The shell keeps its bar — the language control is the one thing a first-run
 * user needs and cannot reach any other way — so the page is one card at the
 * content measure: 28 rem wide, no viewport-tall wrapper. The page names
 * itself the way every page does, through the tab's title stack.
 *
 * A chosen demo is the L2 selection contract: the `--soft` wash and weight,
 * the native radio's own dot beside them — never a filled block. The wash
 * pulls the entry's quiet second line up to foreground, so no muted text
 * sits on `--soft` (the AA rule the parked P1 finding binds). Each demo
 * wears the shell's `Cover` (R41: the tile lives in `web/ui/` now — the
 * second capability needing the engine was the rule's own trigger), so
 * first run meets the same book object the shelf shows.
 */
export function SetupPage() {
  const t = useTranslation();
  const navigate = useNavigate();
  // The tab's name: the page's short word, not the welcome sentence twice —
  // `<page> — Narrare` composes the rest, the way every page does.
  usePageTitle(t("setup.tabTitle"));
  const [title, setTitle] = useState("");
  const [demo, setDemo] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const selected = demo === null ? undefined : DEMOS.find((entry) => entry.slug === demo);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    // A demo names the novel itself, so it submits without a typed title;
    // the blank path still needs one.
    if (!selected && title.trim() === "") return;
    const { data, response } = await client.POST("/api/setup", {
      // The blank path sends no demo at all — absent, not null — so the
      // request an older API sees is byte-for-byte the one it always saw.
      body: {
        novel_title: selected ? selected.title : title,
        ...(selected ? { demo: selected.slug } : {}),
      },
    });
    if (!response.ok || !data) {
      setFailed(true);
      return;
    }
    void navigate({ to: "/novels/$id", params: { id: data.novel_id } });
  }

  return (
    <div className="mx-auto w-full max-w-112 px-4 py-10">
      <Panel>
        <h1 className="text-title font-semibold tracking-tight">{t("setup.welcome")}</h1>
        <p className="mt-2 text-body text-muted">{t("setup.intro")}</p>
        <form onSubmit={submit} className="mt-5 flex flex-col gap-2">
          <Field
            label={t("setup.titleLabel")}
            hint={
              selected
                ? t("setup.demo.titleReplaces", { title: selected.title })
                : undefined
            }
          >
            <Input
              value={title}
              // A demo names the novel itself, so a typed title is parked —
              // visibly disabled, never silently dropped — until blank wins.
              disabled={selected !== undefined}
              onChange={(event) => setTitle(event.target.value)}
            />
          </Field>
          <fieldset className="mt-2 flex flex-col gap-1">
            <legend className="text-label font-medium">{t("setup.demo.heading")}</legend>
            <label className="group flex items-start gap-3 rounded-[var(--radius)] px-2 py-1.5 has-checked:bg-soft">
              <input
                type="radio"
                name="demo"
                value=""
                checked={demo === null}
                onChange={() => setDemo(null)}
                className="mt-1 accent-primary"
              />
              <span className="flex flex-col">
                <span className="text-body font-medium group-has-checked:font-semibold">
                  {t("setup.demo.blank")}
                </span>
                <span className="text-label text-muted group-has-checked:text-foreground">
                  {t("setup.demo.blankHint")}
                </span>
              </span>
            </label>
            {DEMOS.map((entry) => (
              <label
                key={entry.slug}
                className="group flex items-center gap-3 rounded-[var(--radius)] px-2 py-1.5 has-checked:bg-soft"
              >
                <input
                  type="radio"
                  name="demo"
                  value={entry.slug}
                  checked={demo === entry.slug}
                  onChange={() => setDemo(entry.slug)}
                  className="accent-primary"
                />
                {/* The demo's cover: the book a face, the shelf's tile —
                    the object grounds the choice the radio names. The tile
                    is aria-hidden; the radio's name already carries the
                    title, and a second copy of it would read twice. */}
                <Cover title={entry.title} />
                <span className="flex min-w-0 flex-col">
                  <span className="text-body font-medium group-has-checked:font-semibold">
                    {entry.title}
                  </span>
                  <span className="text-label text-muted group-has-checked:text-foreground">
                    {t("setup.demo.language", { language: entry.language })} ·{" "}
                    {t("setup.demo.chapters", { count: entry.chapters })} ·{" "}
                    {t("setup.demo.entities", { count: entry.entities })}
                  </span>
                </span>
              </label>
            ))}
          </fieldset>
          {failed ? (
            <Notice tone="danger" live="alert" className="mt-2">
              {t("setup.failed")}
            </Notice>
          ) : null}
          <Button type="submit" variant="primary" className="mt-2 self-start">
            {t("setup.submit")}
          </Button>
        </form>
      </Panel>
    </div>
  );
}
