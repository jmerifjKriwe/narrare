"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { authApi, setupApi } from "@/lib/api/client";
import { useWizardStore } from "@/lib/stores/wizardStore";
import { cn } from "@/lib/utils";
import { WizardStep1 } from "./WizardStep1";
import { WizardStep2 } from "./WizardStep2";
import { WizardStep3 } from "./WizardStep3";
import { WizardStep4 } from "./WizardStep4";
import { WizardStep5 } from "./WizardStep5";

export function WizardShell() {
  const t = useTranslations("wizard");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const { currentStep, nextStep, prevStep, reset } = useWizardStore();

  const [hasProviders, setHasProviders] = useState(false);
  const [loadingProviders, setLoadingProviders] = useState(true);

  // Check if user already has providers configured
  useEffect(() => {
    authApi
      .me()
      .then((user) => {
        setHasProviders(user.has_providers);
        setLoadingProviders(false);
      })
      .catch(() => {
        setHasProviders(false);
        setLoadingProviders(false);
      });
  }, []);

  // Navigation that skips Step 4 when providers already exist
  const handleNext = () => {
    const next = currentStep + 1;
    if (next === 4 && hasProviders) {
      useWizardStore.getState().setStep(5);
    } else {
      nextStep();
    }
  };

  const handlePrev = () => {
    const prev = currentStep - 1;
    if (prev === 4 && hasProviders) {
      useWizardStore.getState().setStep(3);
    } else {
      prevStep();
    }
  };

  const handleComplete = async () => {
    const currentState = useWizardStore.getState().state;
    // Tell backend to skip provider creation when already configured
    if (hasProviders) {
      useWizardStore.setState({
        state: { ...currentState, skip_provider: true },
      });
    }
    const { state: updatedState } = useWizardStore.getState();
    const result = await setupApi.complete(updatedState);
    reset();
    router.push(result.redirect_to as Parameters<typeof router.push>[0]);
  };

  // Step definitions — Step 4 omitted when providers already configured
  const steps = hasProviders
    ? [
        { label: "1", title: t("step1.title"), step: 1 },
        { label: "2", title: t("step3.title"), step: 2 },
        { label: "3", title: t("step2.title"), step: 3 },
        { label: "4", title: t("step5.title"), step: 5 },
      ]
    : [
        { label: "1", title: t("step1.title"), step: 1 },
        { label: "2", title: t("step3.title"), step: 2 },
        { label: "3", title: t("step2.title"), step: 3 },
        { label: "4", title: t("step4.title"), step: 4 },
        { label: "5", title: t("step5.title"), step: 5 },
      ];

  if (loadingProviders) {
    return (
      <div className="h-full flex items-center justify-center">
        <span className="text-[var(--color-text-tertiary)]">{tCommon("loading")}</span>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-[var(--color-bg-primary)] flex items-start justify-center p-8 px-4">
      <div className="w-full max-w-[640px]">
        {/* Progress line */}
        <div className="flex items-center gap-3 justify-center mb-8">
          <div className="flex items-center">
            {steps.map((step, i) => (
              <div key={step.label} className="flex items-center">
                {i > 0 && (
                  <div
                    className={cn(
                      "w-10 h-[2px] rounded-full transition-all duration-500",
                      step.step < currentStep
                        ? "bg-[var(--color-accent)]"
                        : "bg-[var(--color-border)]",
                    )}
                  />
                )}
                <div
                  className={cn(
                    "w-9 h-9 rounded-full flex items-center justify-center text-xs font-semibold transition-all duration-500 border-2",
                    step.step === currentStep
                      ? "bg-[var(--color-accent)] text-white border-[var(--color-accent)]"
                      : step.step < currentStep
                        ? "bg-[var(--color-accent)] text-white border-[var(--color-accent)]"
                        : "bg-transparent text-[var(--color-text-tertiary)] border-[var(--color-border)]",
                  )}
                  aria-current={step.step === currentStep ? "step" : undefined}
                >
                  {step.step < currentStep ? "✓" : step.label}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Step content card */}
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-10 shadow-[var(--shadow-md)]">
          {currentStep === 1 && <WizardStep1 onNext={handleNext} />}
          {currentStep === 2 && <WizardStep3 onNext={handleNext} onBack={handlePrev} />}
          {currentStep === 3 && <WizardStep2 onNext={handleNext} onBack={handlePrev} />}
          {currentStep === 4 && !hasProviders && (
            <WizardStep4 onNext={handleNext} onBack={handlePrev} />
          )}
          {currentStep === 5 && <WizardStep5 onComplete={handleComplete} onBack={handlePrev} />}
        </div>
      </div>
    </div>
  );
}
