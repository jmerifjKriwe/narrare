"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useTranslations } from "next-intl"
import { useAuthStore } from "@/lib/stores/authStore"
import { Button } from "@/components/ui/Button"
import { Input } from "@/components/ui/Input"

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8, "Password must be at least 8 characters"),
  display_name: z.string().optional(),
})
type FormData = z.infer<typeof schema>

export default function RegisterPage() {
  const t = useTranslations("auth")
  const router = useRouter()
  const register_user = useAuthStore((s) => s.register)
  const [error, setError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) })

  const onSubmit = async (data: FormData) => {
    setError(null)
    try {
      await register_user(data.email, data.password, data.display_name)
      router.push("/wizard")
    } catch {
      setError(t("emailTaken"))
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <h1 className="auth-title">Narrare</h1>
          <p className="auth-subtitle">{t("register")}</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="auth-form">
          {error && <p className="auth-error">{error}</p>}

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

          <Button type="submit" loading={isSubmitting} className="w-full">
            {t("registerButton")}
          </Button>
        </form>

        <p className="auth-footer">
          {t("hasAccount")}{" "}
          <Link href="/login" className="auth-link">
            {t("login")}
          </Link>
        </p>
      </div>

      <style jsx>{`
        .auth-page {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          background-color: var(--color-bg-secondary);
          padding: var(--space-4);
        }
        .auth-card {
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-xl);
          padding: var(--space-8);
          width: 100%;
          max-width: 400px;
          box-shadow: var(--shadow-md);
        }
        .auth-header { text-align: center; margin-bottom: var(--space-6); }
        .auth-title { font-size: 1.75rem; font-weight: 700; letter-spacing: -0.02em; }
        .auth-subtitle { color: var(--color-text-secondary); margin-top: var(--space-1); }
        .auth-form { display: flex; flex-direction: column; gap: var(--space-4); }
        .auth-error {
          background: var(--color-error-light);
          color: var(--color-error);
          border-radius: var(--radius-md);
          padding: var(--space-3);
          font-size: 0.875rem;
        }
        .auth-footer {
          margin-top: var(--space-6);
          text-align: center;
          font-size: 0.875rem;
          color: var(--color-text-secondary);
        }
        .auth-link { color: var(--color-accent); text-decoration: none; font-weight: 500; }
        .auth-link:hover { text-decoration: underline; }
      `}</style>
    </div>
  )
}
