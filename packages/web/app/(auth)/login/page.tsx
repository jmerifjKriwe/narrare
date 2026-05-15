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
      const user = await login(data.email, data.password);
      router.push(user.has_providers ? "/dashboard" : "/wizard");
    } catch {
      setError(t("invalidCredentials"));
    }
  };

  return (
    <div className="min-h-screen relative flex items-center justify-center overflow-hidden bg-background">
      {/* Subtle paper-grain background texture */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.02]"
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
          <h1 className="text-5xl font-bold tracking-[0.08em] text-foreground leading-none font-[family-name:var(--font-display)]">
            Narrare
          </h1>
          {/* Ornamental divider below wordmark */}
          <div className="mt-4 text-muted-foreground/60 text-xs tracking-[0.3em]">— ❧ —</div>
          <p className="text-muted-foreground mt-4 text-[0.9375rem] leading-relaxed font-[family-name:var(--font-serif)] italic">
            {t("login")}
          </p>
        </div>

        {/* Form card — clean with subtle shadow */}
        <div className="bg-card/95 backdrop-blur-sm rounded-2xl p-10 border border-border/80 shadow-lg">
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6">
            {error && (
              <p className="bg-destructive/10 text-destructive rounded-lg p-4 text-sm border-l-2 border-l-destructive">
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
            <Button
              type="submit"
              loading={isSubmitting}
              className="w-full h-11 text-[0.9375rem] mt-2 tracking-wide font-medium"
            >
              {t("loginButton")}
            </Button>
          </form>
        </div>

        {/* Register link — below card, generous spacing */}
        <p className="mt-10 text-center text-sm text-muted-foreground">
          {t("noAccount")}{" "}
          <Link
            href="/register"
            className="text-primary no-underline font-medium hover:text-primary/80 transition-colors"
          >
            {t("register")}
          </Link>
        </p>
      </div>
    </div>
  );
}
