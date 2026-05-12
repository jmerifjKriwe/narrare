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
    <div className="min-h-screen bg-[var(--color-bg-secondary)] flex items-start justify-center p-8 px-4">
      <div className="w-full max-w-[640px]">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-center mb-6 tracking-tight">{t("title")}</h1>
          <ul className="flex gap-2 justify-center flex-wrap" aria-label="Progress">
            {steps.map((step, i) => (
              <li
                key={step.label}
                className={cn(
                  "flex items-center gap-2 text-[0.8125rem]",
                  i + 1 === currentStep
                    ? "[&_.wizard-step-dot]:bg-[var(--color-accent)] [&_.wizard-step-dot]:text-white [&_.wizard-step-label]:text-[var(--color-text-primary)]"
                    : i + 1 < currentStep
                      ? "[&_.wizard-step-dot]:bg-[var(--color-success)] [&_.wizard-step-dot]:text-white"
                      : "[&_.wizard-step-dot]:bg-[var(--color-bg-tertiary)] [&_.wizard-step-dot]:text-[var(--color-text-tertiary)]",
                )}
                aria-current={i + 1 === currentStep ? "step" : undefined}
              >
                <span className="wizard-step-dot w-7 h-7 rounded-full flex items-center justify-center font-semibold text-xs shrink-0">
                  {i + 1 < currentStep ? "✓" : step.label}
                </span>
                <span className="wizard-step-label text-[var(--color-text-secondary)] font-medium">
                  {step.title}
                </span>
              </li>
            ))}
          </ul>
        </div>

        {/* Step content */}
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-xl)] p-8 shadow-[var(--shadow-md)]">
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
