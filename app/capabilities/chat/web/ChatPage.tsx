import { Link } from "@tanstack/react-router";

import { useTranslation } from "@shell/lib/i18n";

import { ChatPanel } from "./ChatPanel";

/** The chat page: its own destination, the shared panel inside. */
export function ChatPage() {
  const t = useTranslation();

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">{t("chat.heading")}</h1>
      <p className="mt-2 text-sm text-muted">
        <Link to="/" className="underline-offset-4 hover:underline">
          {t("nav.back")}
        </Link>
      </p>
      <div className="mt-6">
        <ChatPanel />
      </div>
    </div>
  );
}
