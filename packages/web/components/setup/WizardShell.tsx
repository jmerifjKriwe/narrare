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
    <div className="min-h-screen bg-[var(--color-bg-primary)] flex items-start justify-center p-8 px-4">
      <div className="w-full max-w-[640px]">
        {/* Header with wordmark */}
        <div className="text-center mb-10">
          <h1
            className="text-3xl font-bold tracking-[0.12em] text-[var(--color-text-primary)]"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Narrare
          </h1>
          <p className="text-[var(--color-text-tertiary)] mt-2 text-[0.9375rem]">{t("title")}</p>
        </div>

        {/* Progress line */}
        <div className="flex items-center gap-3 justify-center mb-8">
          {steps.map((step, i) => (
            <div key={step.label} className="flex items-center gap-3">
              {i > 0 && (
                <div
                  className={cn(
                    "w-8 h-[2px] rounded-full transition-colors duration-300",
                    i + 1 <= currentStep ? "bg-[var(--color-accent)]" : "bg-[var(--color-border)]",
                  )}
                />
              )}
              <div
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold transition-all duration-300",
                  i + 1 === currentStep
                    ? "bg-[var(--color-accent)] text-white scale-110"
                    : i + 1 < currentStep
                      ? "bg-[var(--color-accent)] text-white"
                      : "bg-[var(--color-bg-tertiary)] text-[var(--color-text-tertiary)]",
                )}
                aria-current={i + 1 === currentStep ? "step" : undefined}
              >
                {i + 1 < currentStep ? "✓" : step.label}
              </div>
            </div>
          ))}
        </div>

        {/* Step content */}
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-10 shadow-[var(--shadow-md)]">
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
