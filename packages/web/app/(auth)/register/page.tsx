"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useAuthStore } from "@/lib/stores/authStore";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8, "Password must be at least 8 characters"),
  display_name: z.string().optional(),
});
type FormData = z.infer<typeof schema>;

export default function RegisterPage() {
  const t = useTranslations("auth");
  const router = useRouter();
  const register_user = useAuthStore((s) => s.register);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    setError(null);
    try {
      await register_user(data.email, data.password, data.display_name);
      router.push("/wizard");
    } catch {
      setError(t("emailTaken"));
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg-primary)] p-4">
      <div className="w-full max-w-[420px]">
        {/* Wordmark */}
        <div className="text-center mb-10">
          <h1
            className="text-4xl font-bold tracking-[0.15em] text-[var(--color-text-primary)]"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Narrare
          </h1>
          <p className="text-[var(--color-text-tertiary)] mt-2 text-[0.9375rem]">{t("register")}</p>
        </div>

        <div className="bg-[var(--color-surface)] rounded-xl p-10 shadow-[var(--shadow-lg)] border border-[var(--color-border)]">
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-5">
            {error && (
              <p className="bg-[var(--color-error-light)] text-[var(--color-error)] rounded-lg p-3 text-sm border border-[var(--color-error)]/20">
                {error}
              </p>
            )}

            <Input
              {...register("email")}
              type="email"
              label={t("email")}
              placeholder="you@example.com"
              error={errors.email?.message}
              autoComplete="email"
              autoFocus
            />

            <Input
              {...register("display_name")}
              type="text"
              label={t("displayName")}
              placeholder={t("displayNamePlaceholder")}
              autoComplete="name"
            />

            <Input
              {...register("password")}
              type="password"
              label={t("password")}
              error={errors.password?.message}
              autoComplete="new-password"
            />

            <Button type="submit" loading={isSubmitting} className="w-full mt-1">
              {t("registerButton")}
            </Button>
          </form>

          <p className="mt-8 text-center text-sm text-[var(--color-text-tertiary)]">
            {t("hasAccount")}{" "}
            <Link
              href="/login"
              className="text-[var(--color-accent)] no-underline font-medium hover:underline"
            >
              {t("login")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
