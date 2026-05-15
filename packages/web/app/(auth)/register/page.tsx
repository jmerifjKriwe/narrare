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
  const registerUser = useAuthStore((s) => s.register);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    setError(null);
    try {
      const user = await registerUser(data.email, data.password, data.display_name);
      router.push(user.has_providers ? "/dashboard" : "/wizard");
    } catch {
      setError(t("emailTaken"));
    }
  };

  return (
    <div className="min-h-screen relative flex items-center justify-center overflow-hidden bg-[var(--color-bg-primary)]">
      {/* Subtle paper-grain background texture */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.03]"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, var(--color-text-primary) 0.5px, transparent 0.5px)",
          backgroundSize: "24px 24px",
        }}
      />

      {/* Main content */}
      <div className="relative z-10 w-full max-w-[440px] px-6">
        {/* Wordmark — book title page */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold tracking-[0.08em] text-[var(--color-text-primary)] leading-none font-[family-name:var(--font-display)]">
            Narrare
          </h1>
          {/* Ornamental divider below wordmark */}
          <div className="mt-4 text-[var(--color-accent-muted)] text-xs tracking-[0.3em]">
            — ❧ —
          </div>
          <p className="text-[var(--color-text-tertiary)] mt-4 text-[0.9375rem] leading-relaxed font-[family-name:var(--font-serif)] italic">
            {t("register")}
          </p>
        </div>

        {/* Form card — floating with layered depth */}
        <div className="bg-[var(--color-surface)]/90 backdrop-blur-sm rounded-2xl p-12 border border-[var(--color-border)]/40 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.5),0_4px_6px_rgba(44,40,37,0.04),0_12px_24px_rgba(44,40,37,0.08),0_32px_64px_rgba(44,40,37,0.06)]">
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6">
            {error && (
              <p className="bg-[var(--color-error-light)] text-[var(--color-error)] rounded-lg p-4 text-sm border-l-2 border-l-[var(--color-error)]">
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
            <Button
              type="submit"
              loading={isSubmitting}
              className="w-full h-11 text-[0.9375rem] mt-1 tracking-wide"
            >
              {t("registerButton")}
            </Button>
          </form>
        </div>

        {/* Login link — below card, generous spacing */}
        <p className="mt-10 text-center text-sm text-[var(--color-text-tertiary)]">
          {t("hasAccount")}{" "}
          <Link
            href="/login"
            className="text-[var(--color-accent)] no-underline font-medium hover:text-[var(--color-accent-hover)] transition-colors"
          >
            {t("login")}
          </Link>
        </p>
      </div>
    </div>
  );
}
