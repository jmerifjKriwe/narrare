"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { AuthError } from "@/components/auth/AuthError";
import { AuthLayout } from "@/components/auth/AuthLayout";
import { AuthSubmitButton } from "@/components/auth/AuthSubmitButton";
import { RegisterFields } from "@/components/auth/RegisterFields";
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
    <AuthLayout
      title={t("registerTitle")}
      subtitle={t("registerSubtitle")}
      footerText={t("hasAccount")}
      footerLinkHref="/login"
      footerLinkText={t("signIn")}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && <AuthError message={error} />}

        <RegisterFields
          displayName={displayName}
          email={email}
          password={password}
          onDisplayNameChange={setDisplayName}
          onEmailChange={setEmail}
          onPasswordChange={setPassword}
          t={t}
        />

        <AuthSubmitButton
          isSubmitting={isSubmitting}
          loadingLabel={t("loading")}
          submitLabel={t("registerButton")}
        />
      </form>
    </AuthLayout>
  );
}
