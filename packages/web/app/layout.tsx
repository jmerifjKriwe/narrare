import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import { AuthProvider } from "@/components/shared/AuthProvider";
import { MotionProvider } from "@/components/shared/MotionProvider";
import { QueryProvider } from "@/components/shared/QueryProvider";
import { ThemeProvider } from "@/components/shared/ThemeProvider";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: { default: "Narrare", template: "%s | Narrare" },
  description: "AI-assisted creative writing environment",
  // Tell the browser the page is designed for dark and light color schemes so
  // native controls (scrollbars, form widgets) adapt to the active theme.
  colorScheme: "dark light",
  icons: {
    icon: "/favicon.png",
  },
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale} suppressHydrationWarning>
      <head>
        <script
          // biome-ignore lint/security/noDangerouslySetInnerHtml: inline FOUC-prevention script must run before paint
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var s=JSON.parse(localStorage.getItem('narrare-theme'));var t=(s&&s.state&&s.state.theme)||'neutral';var m=(s&&s.state&&s.state.colorMode)||'system';document.documentElement.setAttribute('data-theme',t);if(m==='dark'||(m==='system'&&window.matchMedia('(prefers-color-scheme:dark)').matches)){document.documentElement.classList.add('dark')}}catch(e){document.documentElement.setAttribute('data-theme','neutral')}})()`,
          }}
        />
      </head>
      <body>
        <NextIntlClientProvider messages={messages}>
          <MotionProvider>
            <QueryProvider>
              <ThemeProvider />
              <AuthProvider>{children}</AuthProvider>
            </QueryProvider>
          </MotionProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
