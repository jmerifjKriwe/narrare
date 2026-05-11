import type { Metadata } from "next"
import { NextIntlClientProvider } from "next-intl"
import { getLocale, getMessages } from "next-intl/server"
import { QueryProvider } from "@/components/shared/QueryProvider"
import "@/styles/globals.css"

export const metadata: Metadata = {
  title: {
    default: "Narrare",
    template: "%s | Narrare",
  },
  description: "AI-assisted creative writing environment",
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const locale = await getLocale()
  const messages = await getMessages()

  return (
    <html lang={locale} suppressHydrationWarning>
      <body>
        <NextIntlClientProvider messages={messages}>
          <QueryProvider>{children}</QueryProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  )
}
