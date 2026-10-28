import { useNavigate } from "@tanstack/react-router";
import { useId, useState } from "react";

import { client } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";

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

/** The setup page: start blank or from a demo, then straight into the editor. */
export function SetupPage() {
  const t = useTranslation();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [demo, setDemo] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const selected = demo === null ? undefined : DEMOS.find((entry) => entry.slug === demo);
  const titleHintId = useId();

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
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-10">
      <div className="rounded-lg border border-border bg-card p-8">
        <h1 className="text-2xl font-semibold tracking-tight">{t("setup.welcome")}</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted">{t("setup.intro")}</p>
        <form onSubmit={submit} className="mt-6 flex flex-col gap-2">
          <label className="flex flex-col gap-1 text-sm font-medium">
            {t("setup.titleLabel")}
            <input
              value={title}
              // A demo names the novel itself, so a typed title is parked —
              // visibly disabled, never silently dropped — until blank wins.
              disabled={selected !== undefined}
              aria-describedby={selected !== undefined ? titleHintId : undefined}
              onChange={(event) => setTitle(event.target.value)}
              className="rounded-md border border-border bg-background px-3 py-2 text-base font-normal focus:border-primary focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
            />
          </label>
          {selected ? (
            <p id={titleHintId} className="text-sm text-muted">
              {t("setup.demo.titleReplaces", { title: selected.title })}
            </p>
          ) : null}
          <fieldset className="mt-2 flex flex-col gap-2">
            <legend className="text-sm font-medium">{t("setup.demo.heading")}</legend>
            <label className="flex items-start gap-3 rounded-md border border-border px-3 py-2 text-sm has-checked:border-primary">
              <input
                type="radio"
                name="demo"
                value=""
                checked={demo === null}
                onChange={() => setDemo(null)}
                className="mt-1 accent-primary"
              />
              <span className="flex flex-col">
                <span className="font-medium">{t("setup.demo.blank")}</span>
                <span className="text-muted">{t("setup.demo.blankHint")}</span>
              </span>
            </label>
            {DEMOS.map((entry) => (
              <label
                key={entry.slug}
                className="flex items-start gap-3 rounded-md border border-border px-3 py-2 text-sm has-checked:border-primary"
              >
                <input
                  type="radio"
                  name="demo"
                  value={entry.slug}
                  checked={demo === entry.slug}
                  onChange={() => setDemo(entry.slug)}
                  className="mt-1 accent-primary"
                />
                <span className="flex flex-col">
                  <span className="font-medium">{entry.title}</span>
                  <span className="text-muted">
                    {t("setup.demo.language", { language: entry.language })} ·{" "}
                    {t("setup.demo.chapters", { count: entry.chapters })} ·{" "}
                    {t("setup.demo.entities", { count: entry.entities })}
                  </span>
                </span>
              </label>
            ))}
          </fieldset>
          {failed ? (
            <p role="alert" className="text-sm text-danger">
              {t("setup.failed")}
            </p>
          ) : null}
          <button
            type="submit"
            className="mt-2 self-start rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
          >
            {t("setup.submit")}
          </button>
        </form>
      </div>
    </div>
  );
}
