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
  password: z.string().min(1),
});
type FormData = z.infer<typeof schema>;

export default function LoginPage() {
  const t = useTranslations("auth");
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    setError(null);
    try {
      await login(data.email, data.password);
      router.push("/dashboard");
    } catch {
      setError(t("invalidCredentials"));
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg-secondary)] p-4">
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-xl)] p-8 w-full max-w-[400px] shadow-[var(--shadow-md)]">
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold text-[var(--color-text-primary)] tracking-tight font-[family-name:var(--font-serif)]">
            Narrare
          </h1>
          <p className="text-[var(--color-text-secondary)] mt-1">{t("login")}</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          {error && (
            <p className="bg-[var(--color-error-light)] text-[var(--color-error)] rounded-[var(--radius-md)] p-3 text-sm">
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
            {...register("password")}
            type="password"
            label={t("password")}
            error={errors.password?.message}
            autoComplete="current-password"
          />

          <Button type="submit" loading={isSubmitting} className="w-full">
            {t("loginButton")}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-[var(--color-text-secondary)]">
          {t("noAccount")}{" "}
          <Link
            href="/register"
            className="text-[var(--color-accent)] no-underline font-medium hover:underline"
          >
            {t("register")}
          </Link>
        </p>
      </div>
    </div>
  );
}
