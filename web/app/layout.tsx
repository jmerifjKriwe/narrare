import type { Metadata } from "next";

import { t } from "../lib/i18n";
import "./globals.css";

export const metadata: Metadata = { title: t("app.title") };

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="de">
      <body className="bg-background text-foreground min-h-screen antialiased">
        {children}
      </body>
    </html>
  );
}
