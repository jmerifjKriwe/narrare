"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { setupApi } from "@/lib/api/client";
import { useWizardStore } from "@/lib/stores/wizardStore";
import { cn } from "@/lib/utils";
import { WizardStep1 } from "./WizardStep1";
import { WizardStep2 } from "./WizardStep2";
import { WizardStep3 } from "./WizardStep3";
import { WizardStep4 } from "./WizardStep4";
import { WizardStep5 } from "./WizardStep5";

export function WizardShell() {
  const t = useTranslations("wizard");
  const router = useRouter();
  const { currentStep, nextStep, prevStep, state, reset } = useWizardStore();

  const handleComplete = async () => {
    const result = await setupApi.complete(state);
    reset();
    router.push(result.redirect_to as Parameters<typeof router.push>[0]);
  };

  const steps = [
    { label: "1", title: t("step1.title") },
    { label: "2", title: t("step2.title") },
    { label: "3", title: t("step3.title") },
    { label: "4", title: t("step4.title") },
    { label: "5", title: t("step5.title") },
  ];

  return (
    <div
      className="min-h-screen flex items-center justify-center relative overflow-hidden"
      style={{ background: "linear-gradient(160deg, #FAF8F3 0%, #F3EDE3 40%, #EDE4D8 100%)" }}
    >
      {/* Decorative background */}
      <div
        className="absolute -top-40 -right-40 w-[600px] h-[600px] rounded-full opacity-[0.05] pointer-events-none"
        style={{ background: "radial-gradient(circle, #B8621B, transparent 70%)" }}
      />

      <div className="relative z-10 w-full max-w-[640px] px-6">
        {/* Header — dramatic wordmark */}
        <div className="text-center mb-12">
          <div className="text-[var(--color-accent-muted)] text-xs tracking-[0.3em] mb-4">✦</div>
          <h1
            className="text-4xl font-bold tracking-[0.08em] text-[var(--color-text-primary)] leading-none"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Narrare
          </h1>
          <p
            className="text-[var(--color-text-tertiary)] mt-4 text-[0.9375rem]"
            style={{ fontFamily: "var(--font-serif)", fontStyle: "italic" }}
          >
            {t("title")}
          </p>
        </div>

        {/* Progress — elegant connected line */}
        <div className="flex items-center justify-center mb-10">
          <div className="flex items-center">
            {steps.map((step, i) => (
              <div key={step.label} className="flex items-center">
                {i > 0 && (
                  <div
                    className={cn(
                      "w-10 h-[2px] rounded-full transition-all duration-500",
                      i < currentStep ? "bg-[var(--color-accent)]" : "bg-[var(--color-border)]",
                    )}
                  />
                )}
                <div
                  className={cn(
                    "w-9 h-9 rounded-full flex items-center justify-center text-xs font-semibold transition-all duration-500 border-2",
                    i + 1 === currentStep
                      ? "bg-[var(--color-accent)] text-white border-[var(--color-accent)]"
                      : i + 1 < currentStep
                        ? "bg-[var(--color-accent)] text-white border-[var(--color-accent)]"
                        : "bg-transparent text-[var(--color-text-tertiary)] border-[var(--color-border)]",
                  )}
                  aria-current={i + 1 === currentStep ? "step" : undefined}
                >
                  {i + 1 < currentStep ? "✓" : step.label}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Step content card */}
        <div
          className="bg-[var(--color-surface)]/90 backdrop-blur-sm rounded-2xl p-10 border border-[var(--color-border)]/60"
          style={{
            boxShadow:
              "0 4px 6px rgba(44,40,37,0.04), 0 12px 24px rgba(44,40,37,0.08), 0 32px 64px rgba(44,40,37,0.06)",
          }}
        >
          {currentStep === 1 && <WizardStep1 onNext={nextStep} />}
          {currentStep === 2 && <WizardStep2 onNext={nextStep} onBack={prevStep} />}
          {currentStep === 3 && <WizardStep3 onNext={nextStep} onBack={prevStep} />}
          {currentStep === 4 && <WizardStep4 onNext={nextStep} onBack={prevStep} />}
          {currentStep === 5 && <WizardStep5 onComplete={handleComplete} onBack={prevStep} />}
        </div>
      </div>
    </div>
  );
}
