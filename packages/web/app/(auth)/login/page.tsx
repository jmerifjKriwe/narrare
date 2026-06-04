"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { AuthError } from "@/components/auth/AuthError";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { AuthSubmitButton } from "@/components/auth/AuthSubmitButton";
import { useAuthStore } from "@/lib/stores/authStore";

export default function LoginPage() {
  const t = useTranslations("studio.auth");
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      router.push("/");
    } catch {
      setError(t("loginError"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout
      title={t("loginTitle")}
      subtitle={t("loginSubtitle")}
      footerText={t("noAccount")}
      footerLinkHref="/register"
      footerLinkText={t("signUp")}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && <AuthError message={error} />}

        <div className="flex flex-col gap-1.5">
          <label htmlFor="login-email" className="text-sm font-medium text-foreground">
            {t("email")}
          </label>
          <input
            id="login-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t("emailPlaceholder")}
            autoComplete="email"
            // biome-ignore lint/a11y/noAutofocus: intentional focus on login email field
            autoFocus
            className="h-9 w-full rounded-md border border-border bg-background px-3 py-1 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="login-password" className="text-sm font-medium text-foreground">
            {t("password")}
          </label>
          <input
            id="login-password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={t("passwordPlaceholder")}
            autoComplete="current-password"
            className="h-9 w-full rounded-md border border-border bg-background px-3 py-1 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
          />
        </div>

        <AuthSubmitButton
          isSubmitting={isSubmitting}
          loadingLabel={t("loading")}
          submitLabel={t("loginButton")}
        />
      </form>
    </AuthLayout>
  );
}
