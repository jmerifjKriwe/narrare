"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { t } from "../../lib/i18n";

export default function SetupPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [failed, setFailed] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (title.trim() === "") return;
    const response = await fetch("/api/setup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ novel_title: title }),
    });
    if (!response.ok) {
      setFailed(true);
      return;
    }
    const result: { novel_id: string } = await response.json();
    router.push(`/novels/${result.novel_id}`);
  }

  return (
    <main>
      <h1>{t("setup.welcome")}</h1>
      <p>{t("setup.intro")}</p>
      <form onSubmit={submit}>
        <label>
          {t("setup.titleLabel")}
          <input value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>
        {failed ? <p role="alert">{t("setup.failed")}</p> : null}
        <button type="submit">{t("setup.submit")}</button>
      </form>
    </main>
  );
}
