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
        <span className="text-muted-foreground animate-pulse">{tCommon("loading")}...</span>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-background flex items-start justify-center p-8 px-4">
      <div className="w-full max-w-[640px] pt-8">
        {/* Progress line */}
        <div className="flex items-center justify-center mb-10 px-4">
          <div className="flex items-center w-full max-w-[400px]">
            {steps.map((step, i) => (
              <div key={step.label} className="flex items-center flex-1 last:flex-none">
                <div className="flex flex-col items-center gap-2 relative">
                  <div
                    className={cn(
                      "w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold transition-all duration-500 border-2 relative z-10",
                      step.step === currentStep
                        ? "bg-primary text-primary-foreground border-primary shadow-sm"
                        : step.step < currentStep
                          ? "bg-primary text-primary-foreground border-primary"
                          : "bg-card text-muted-foreground border-border",
                    )}
                    aria-current={step.step === currentStep ? "step" : undefined}
                  >
                    {step.step < currentStep ? "✓" : step.label}
                  </div>
                  {/* Optional label below bubble */}
                  <span
                    className={cn(
                      "absolute top-12 whitespace-nowrap text-xs font-medium transition-colors duration-300",
                      step.step === currentStep
                        ? "text-foreground"
                        : "text-muted-foreground opacity-0 sm:opacity-100",
                    )}
                  >
                    {step.title}
                  </span>
                </div>
                {i < steps.length - 1 && (
                  <div
                    className={cn(
                      "flex-1 h-[2px] -mx-1 transition-all duration-500",
                      steps[i + 1].step <= currentStep ? "bg-primary" : "bg-border",
                    )}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Step content card */}
        <div className="bg-card border border-border rounded-2xl p-10 shadow-lg mt-8">
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
