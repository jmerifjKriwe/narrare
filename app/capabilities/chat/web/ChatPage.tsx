import { Link } from "@tanstack/react-router";

import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";

import { ChatPanel } from "./ChatPanel";

/** The chat page: its own destination, the shared panel inside. */
export function ChatPage() {
  const t = useTranslation();
  // The tab's name: this page is "Chat" until it goes.
  usePageTitle(t("chat.heading"));

  return (
    <div className="mx-auto max-w-[40rem] px-4 py-10">
      <h1 className="text-title font-semibold tracking-tight">{t("chat.heading")}</h1>
      <p className="mt-2 text-body text-muted">
        <Link
          to="/"
          className="underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          {t("nav.back")}
        </Link>
      </p>
      <div className="mt-6">
        <ChatPanel />
      </div>
    </div>
  );
}
