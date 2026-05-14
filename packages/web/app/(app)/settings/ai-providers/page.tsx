"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { ApiKeyDisplay } from "@/components/settings/ApiKeyDisplay";
import { ProviderForm } from "@/components/settings/ProviderForm";
import { Button } from "@/components/ui/Button";
import { aiSettingsApi } from "@/lib/api/client";
import { getProviderLabel } from "@/lib/providers";
import { cn } from "@/lib/utils";
import type { UserProvider } from "@/types";

export default function AiProvidersPage() {
  const t = useTranslations("settings-ai.providersPage");
  const [providers, setProviders] = useState<UserProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingProvider, setEditingProvider] = useState<UserProvider | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadProviders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await aiSettingsApi.listProviders();
      setProviders(result);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t("title");
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  const handleSaved = (_provider: UserProvider) => {
    setShowForm(false);
    setEditingProvider(null);
    loadProviders();
  };

  const handleEdit = (provider: UserProvider) => {
    setEditingProvider(provider);
    setShowForm(true);
  };

  const handleCancel = () => {
    setShowForm(false);
    setEditingProvider(null);
  };

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await aiSettingsApi.deleteProvider(id);
      setProviders((prev) => prev.filter((p) => p.id !== id));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t("delete");
      setError(msg);
    } finally {
      setDeletingId(null);
    }
  };

  const handleToggleActive = async (provider: UserProvider) => {
    try {
      await aiSettingsApi.updateProvider(provider.id, {
        is_active: !provider.is_active,
      });
      loadProviders();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t("edit");
      setError(msg);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <span className="text-[var(--color-text-tertiary)]">{t("loading")}</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-text-primary)]">{t("title")}</h1>
          <p className="text-[0.875rem] text-[var(--color-text-secondary)] mt-1">
            {t("description")}
          </p>
        </div>
        {!showForm && (
          <Button type="button" onClick={() => setShowForm(true)}>
            {t("addProvider")}
          </Button>
        )}
      </div>

      {showForm && (
        <div className="border border-[var(--color-border)] rounded-xl p-6 bg-[var(--color-surface)]">
          <h2 className="text-[0.9375rem] font-semibold text-[var(--color-text-primary)] mb-4">
            {editingProvider ? t("editProvider") : t("addNewProvider")}
          </h2>
          <ProviderForm
            existingProvider={editingProvider}
            onSaved={handleSaved}
            onCancel={handleCancel}
          />
        </div>
      )}

      {error && (
        <div
          className="bg-[var(--color-error)]/10 text-[var(--color-error)] rounded-lg p-3 text-[0.875rem]"
          role="alert"
        >
          {error}
        </div>
      )}

      {providers.length === 0 && !showForm ? (
        <div className="text-center py-16 border border-dashed border-[var(--color-border)] rounded-xl">
          <div className="flex flex-col items-center gap-3">
            <span className="text-[var(--color-text-tertiary)] text-4xl">🔌</span>
            <p className="text-[var(--color-text-secondary)]">{t("empty")}</p>
            <Button type="button" onClick={() => setShowForm(true)}>
              {t("addProvider")}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {providers.map((provider) => (
            <div
              key={provider.id}
              className={cn(
                "border rounded-xl p-5 transition-colors",
                provider.is_active
                  ? "border-[var(--color-border)] bg-[var(--color-surface)]"
                  : "border-[var(--color-border)] bg-[var(--color-bg-secondary)]/50 opacity-70",
              )}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-[0.9375rem] font-medium text-[var(--color-text-primary)]">
                      {getProviderLabel(provider.provider_name)}
                    </span>
                    <span
                      className={cn(
                        "text-[0.625rem] font-medium px-2 py-0.5 rounded-full uppercase tracking-wider",
                        provider.is_active
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-500",
                      )}
                    >
                      {provider.is_active ? t("statusActive") : t("statusInactive")}
                    </span>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <ApiKeyDisplay
                      last4={provider.api_key_last4}
                      hasKey={provider.has_api_key}
                      onChange={() => handleEdit(provider)}
                    />
                    {!provider.has_api_key && provider.provider_name !== "ollama" && (
                      <p className="text-[0.8125rem] text-[var(--color-text-tertiary)] italic">
                        {t("addKeyHint")}
                      </p>
                    )}
                    {provider.base_url ? (
                      <p className="text-[0.75rem] text-[var(--color-text-tertiary)]">
                        {t("baseUrl")}
                        {provider.base_url}
                      </p>
                    ) : provider.provider_name === "zai" ? (
                      <p className="text-[0.75rem] text-[var(--color-text-tertiary)]">
                        {t("baseUrl")}
                        {t("defaultBaseUrl")}
                      </p>
                    ) : null}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => handleToggleActive(provider)}
                  >
                    {provider.is_active ? t("deactivate") : t("activate")}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => handleEdit(provider)}
                  >
                    {t("edit")}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    loading={deletingId === provider.id}
                    onClick={() => handleDelete(provider.id)}
                    className="text-[var(--color-error)] hover:text-[var(--color-error)]"
                  >
                    {t("delete")}
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
