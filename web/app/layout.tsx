import type { Metadata } from "next";

import { t } from "../lib/i18n";

export const metadata: Metadata = { title: t("app.title") };

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}
