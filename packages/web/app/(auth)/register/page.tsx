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
    <div
      className="min-h-screen relative flex items-center justify-center overflow-hidden"
      style={{ background: "linear-gradient(160deg, #FAF8F3 0%, #F3EDE3 40%, #EDE4D8 100%)" }}
    >
      {/* Decorative background elements */}
      <div className="absolute inset-0 pointer-events-none">
        {/* Large warm circle — top right */}
        <div
          className="absolute -top-32 -right-32 w-[500px] h-[500px] rounded-full opacity-[0.07]"
          style={{ background: "radial-gradient(circle, #B8621B, transparent 70%)" }}
        />
        {/* Smaller warm circle — bottom left */}
        <div
          className="absolute -bottom-24 -left-24 w-[300px] h-[300px] rounded-full opacity-[0.05]"
          style={{ background: "radial-gradient(circle, #D4A574, transparent 70%)" }}
        />
      </div>

      {/* Main content */}
      <div className="relative z-10 w-full max-w-[440px] px-6">
        {/* Wordmark — DRAMATIC */}
        <div className="text-center mb-12">
          <div className="inline-block mb-4 text-[var(--color-accent-muted)] text-xs tracking-[0.3em] uppercase">
            ✦
          </div>
          <h1
            className="text-5xl font-bold tracking-[0.08em] text-[var(--color-text-primary)] leading-none"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Narrare
          </h1>
          <p
            className="text-[var(--color-text-tertiary)] mt-4 text-[0.9375rem] leading-relaxed"
            style={{ fontFamily: "var(--font-serif)", fontStyle: "italic" }}
          >
            {t("register")}
          </p>
        </div>

        {/* Form card — floating with layered depth */}
        <div
          className="bg-[var(--color-surface)]/90 backdrop-blur-sm rounded-2xl p-10 border border-[var(--color-border)]/60"
          style={{
            boxShadow:
              "0 4px 6px rgba(44,40,37,0.04), 0 12px 24px rgba(44,40,37,0.08), 0 32px 64px rgba(44,40,37,0.06)",
          }}
        >
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6">
            {error && (
              <p className="bg-[var(--color-error-light)] text-[var(--color-error)] rounded-xl p-4 text-sm border border-[var(--color-error)]/15">
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
              className="w-full h-11 text-[0.9375rem] mt-1"
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
