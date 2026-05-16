"use client";

import { BookOpen } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useAuthStore } from "@/lib/stores/authStore";

export default function RegisterPage() {
  const t = useTranslations("studio.auth");
  const router = useRouter();
  const registerUser = useAuthStore((s) => s.register);
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await registerUser(email, password, displayName || undefined);
      router.push("/");
    } catch {
      setError(t("registerError"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-sm">
      {/* Logo */}
      <div className="flex justify-center mb-8">
        <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center">
          <BookOpen className="w-5 h-5 text-primary-foreground" />
        </div>
      </div>

      {/* Card */}
      <div className="bg-card border border-border rounded-xl shadow-lg p-8">
        <h1 className="text-xl font-semibold text-foreground text-center mb-1">
          {t("registerTitle")}
        </h1>
        <p className="text-sm text-muted-foreground text-center mb-6">{t("registerSubtitle")}</p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {error && (
            <div className="bg-destructive/10 text-destructive rounded-md p-3 text-sm border-l-2 border-l-destructive">
              {error}
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <label htmlFor="register-display-name" className="text-sm font-medium text-foreground">
              {t("displayName")}
            </label>
            <input
              id="register-display-name"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={t("displayNamePlaceholder")}
              autoComplete="name"
              className="h-9 w-full rounded-md border border-border bg-background px-3 py-1 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="register-email" className="text-sm font-medium text-foreground">
              {t("email")}
            </label>
            <input
              id="register-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("emailPlaceholder")}
              autoComplete="email"
              // biome-ignore lint/a11y/noAutofocus: intentional focus on register email field
              autoFocus
              className="h-9 w-full rounded-md border border-border bg-background px-3 py-1 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="register-password" className="text-sm font-medium text-foreground">
              {t("password")}
            </label>
            <input
              id="register-password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t("passwordPlaceholder")}
              autoComplete="new-password"
              className="h-9 w-full rounded-md border border-border bg-background px-3 py-1 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-2 h-9 w-full rounded-md bg-primary text-primary-foreground text-sm font-medium shadow-sm hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 disabled:opacity-50 disabled:pointer-events-none transition-colors"
          >
            {isSubmitting ? t("loading") : t("registerButton")}
          </button>
        </form>
      </div>

      {/* Login link */}
      <p className="mt-6 text-center text-sm text-muted-foreground">
        {t("hasAccount")}{" "}
        <Link
          href="/login"
          className="text-primary font-medium hover:text-primary/80 transition-colors no-underline"
        >
          {t("signIn")}
        </Link>
      </p>
    </div>
  );
}
