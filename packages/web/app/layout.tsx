import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import { QueryProvider } from "@/components/shared/QueryProvider";
import { ThemeProvider } from "@/components/shared/ThemeProvider";
import "@/styles/globals.css";
import { DM_Sans, Literata, Playfair_Display } from "next/font/google";
import { cn } from "@/lib/utils";

const display = Playfair_Display({
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-display",
});

const ui = DM_Sans({
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600"],
  variable: "--font-ui",
});

const prose = Literata({
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-prose",
});

export const metadata: Metadata = {
  title: {
    default: "Narrare",
    template: "%s | Narrare",
  },
  description: "AI-assisted creative writing environment",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html
      lang={locale}
      suppressHydrationWarning
      className={cn("font-ui", display.variable, ui.variable, prose.variable)}
    >
      <body>
        <NextIntlClientProvider messages={messages}>
          <QueryProvider>
            <ThemeProvider />
            {children}
          </QueryProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
