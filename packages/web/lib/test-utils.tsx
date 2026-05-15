import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import enGeneration from "../../i18n/messages/en/generation.json";
import enSettings from "../../i18n/messages/en/settings.json";
import enSettingsAi from "../../i18n/messages/en/settings-ai.json";

const messages = {
  settings: enSettings,
  "settings-ai": enSettingsAi,
  generation: enGeneration,
};

/**
 * Create a QueryClient for tests with no retries and no stale time.
 */
function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

/**
 * Wrapper that provides NextIntl + TanStack Query context for tests.
 */
export function createTestWrapper() {
  const queryClient = createTestQueryClient();

  return function TestWrapper({ children }: { children: ReactNode }) {
    return (
      <NextIntlClientProvider locale="en" messages={messages}>
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      </NextIntlClientProvider>
    );
  };
}
