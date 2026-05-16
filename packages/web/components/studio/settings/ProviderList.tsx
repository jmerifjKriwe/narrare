"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { aiSettingsApi } from "@/lib/api/client";
import type { CreateProviderRequest, UpdateProviderRequest, UserProvider } from "@/types";
import { ProviderForm, providerLabel } from "./ProviderForm";

// --- Component ---

interface ProviderListProps {
  readonly providers: readonly UserProvider[];
  readonly isLoading: boolean;
}

export function ProviderList({ providers, isLoading }: ProviderListProps) {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();

  const [showAddForm, setShowAddForm] = useState(false);
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const createProviderMutation = useMutation({
    mutationFn: (data: CreateProviderRequest) => aiSettingsApi.createProvider(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "ai", "providers"] });
      setShowAddForm(false);
    },
    onError: (err) => console.error("Failed to create provider:", err),
  });

  const updateProviderMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: UpdateProviderRequest }) =>
      aiSettingsApi.updateProvider(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "ai", "providers"] });
      setEditingProviderId(null);
    },
    onError: (err) => console.error("Failed to update provider:", err),
  });

  const deleteProviderMutation = useMutation({
    mutationFn: (id: string) => aiSettingsApi.deleteProvider(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "ai", "providers"] });
      setConfirmDeleteId(null);
    },
    onError: (err) => console.error("Failed to delete provider:", err),
  });

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
            <span className="text-lg">🤖</span>
          </div>
          <div>
            <h3 className="font-medium">{t("settings.ai.provider")}</h3>
            <p className="text-sm text-muted-foreground">{t("settings.ai.providerDescription")}</p>
          </div>
        </div>
        {!showAddForm && (
          <button
            type="button"
            onClick={() => setShowAddForm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>{t("settings.ai.addProvider")}</span>
          </button>
        )}
      </div>

      {showAddForm && (
        <ProviderForm
          mode="add"
          onSubmit={(data) => createProviderMutation.mutate(data as CreateProviderRequest)}
          onCancel={() => setShowAddForm(false)}
          isPending={createProviderMutation.isPending}
          t={t}
        />
      )}

      {!showAddForm && (
        <div className="ml-15 space-y-2">
          {providers.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-sm text-muted-foreground">{t("settings.ai.noProviders")}</p>
              <p className="text-xs text-muted-foreground mt-1">
                {t("settings.ai.noProvidersDescription")}
              </p>
            </div>
          ) : (
            providers.map((provider) => (
              <div
                key={provider.id}
                className="flex items-center justify-between p-4 rounded-lg border border-border bg-background"
              >
                <div className="flex items-center gap-3">
                  <div>
                    <p className="text-sm font-medium">{provider.provider_name}</p>
                    {provider.has_api_key && provider.api_key_last4 && (
                      <p className="text-xs text-muted-foreground">••••{provider.api_key_last4}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {editingProviderId === provider.id ? (
                    <ProviderForm
                      mode="edit"
                      initialProviderName={provider.provider_name}
                      initialBaseUrl={provider.base_url}
                      hasKey={provider.has_api_key}
                      last4={provider.api_key_last4}
                      onSubmit={(data) =>
                        updateProviderMutation.mutate({
                          id: provider.id,
                          data: data as UpdateProviderRequest,
                        })
                      }
                      onCancel={() => setEditingProviderId(null)}
                      isPending={updateProviderMutation.isPending}
                      t={t}
                    />
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => setEditingProviderId(provider.id)}
                        className="px-3 py-1.5 text-xs bg-muted rounded-md hover:bg-accent transition-colors"
                      >
                        {t("settings.ai.editApiKey")}
                      </button>
                      {confirmDeleteId === provider.id ? (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">
                            {t("settings.ai.confirmDelete")}
                          </span>
                          <button
                            type="button"
                            onClick={() => deleteProviderMutation.mutate(provider.id)}
                            disabled={deleteProviderMutation.isPending}
                            className="px-3 py-1.5 text-xs bg-destructive text-destructive-foreground rounded-md hover:opacity-90 transition-opacity disabled:opacity-50"
                          >
                            {t("settings.ai.deleteProvider")}
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmDeleteId(null)}
                            className="px-3 py-1.5 text-xs bg-muted rounded-md hover:bg-accent transition-colors"
                          >
                            {t("settings.ai.cancel")}
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setConfirmDeleteId(provider.id)}
                          className="p-1.5 text-muted-foreground hover:text-foreground transition-colors"
                          aria-label={t("settings.ai.deleteProvider")}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
