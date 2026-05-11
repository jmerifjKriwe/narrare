"use client"

import { useRouter } from "next/navigation"
import { useTranslations } from "next-intl"
import { useWizardStore } from "@/lib/stores/wizardStore"
import { setupApi } from "@/lib/api/client"
import { WizardStep1 } from "./WizardStep1"
import { WizardStep2 } from "./WizardStep2"
import { WizardStep3 } from "./WizardStep3"
import { WizardStep4 } from "./WizardStep4"
import { WizardStep5 } from "./WizardStep5"

export function WizardShell() {
  const t = useTranslations("wizard")
  const router = useRouter()
  const { currentStep, nextStep, prevStep, state, reset } = useWizardStore()

  const handleComplete = async () => {
    const result = await setupApi.complete(state)
    reset()
    router.push(result.redirect_to)
  }

  const steps = [
    { label: "1", title: t("step1.title") },
    { label: "2", title: t("step2.title") },
    { label: "3", title: t("step3.title") },
    { label: "4", title: t("step4.title") },
    { label: "5", title: t("step5.title") },
  ]

  return (
    <div className="wizard-page">
      <div className="wizard-container">
        {/* Header */}
        <div className="wizard-header">
          <h1 className="wizard-title">{t("title")}</h1>
          <div className="wizard-progress" role="list" aria-label="Progress">
            {steps.map((step, i) => (
              <div
                key={i}
                role="listitem"
                className={`wizard-step ${
                  i + 1 === currentStep
                    ? "wizard-step--active"
                    : i + 1 < currentStep
                    ? "wizard-step--done"
                    : "wizard-step--pending"
                }`}
                aria-current={i + 1 === currentStep ? "step" : undefined}
              >
                <span className="wizard-step-dot">{i + 1 < currentStep ? "✓" : step.label}</span>
                <span className="wizard-step-label">{step.title}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Step content */}
        <div className="wizard-content">
          {currentStep === 1 && <WizardStep1 onNext={nextStep} />}
          {currentStep === 2 && <WizardStep2 onNext={nextStep} onBack={prevStep} />}
          {currentStep === 3 && <WizardStep3 onNext={nextStep} onBack={prevStep} />}
          {currentStep === 4 && <WizardStep4 onNext={nextStep} onBack={prevStep} />}
          {currentStep === 5 && (
            <WizardStep5 onComplete={handleComplete} onBack={prevStep} />
          )}
        </div>
      </div>

      <style jsx>{`
        .wizard-page {
          min-height: 100vh;
          background: var(--color-bg-secondary);
          display: flex;
          align-items: flex-start;
          justify-content: center;
          padding: var(--space-8) var(--space-4);
        }
        .wizard-container {
          width: 100%;
          max-width: 640px;
        }
        .wizard-header {
          margin-bottom: var(--space-8);
        }
        .wizard-title {
          font-size: 1.5rem;
          font-weight: 700;
          text-align: center;
          margin-bottom: var(--space-6);
          letter-spacing: -0.02em;
        }
        .wizard-progress {
          display: flex;
          gap: var(--space-2);
          justify-content: center;
          flex-wrap: wrap;
        }
        .wizard-step {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          font-size: 0.8125rem;
        }
        .wizard-step-dot {
          width: 1.75rem;
          height: 1.75rem;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: 600;
          font-size: 0.75rem;
          flex-shrink: 0;
        }
        .wizard-step--active .wizard-step-dot {
          background: var(--color-accent);
          color: white;
        }
        .wizard-step--done .wizard-step-dot {
          background: var(--color-success);
          color: white;
        }
        .wizard-step--pending .wizard-step-dot {
          background: var(--color-bg-tertiary);
          color: var(--color-text-tertiary);
        }
        .wizard-step-label {
          color: var(--color-text-secondary);
          font-weight: 500;
        }
        .wizard-step--active .wizard-step-label {
          color: var(--color-text-primary);
        }
        .wizard-content {
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: var(--radius-xl);
          padding: var(--space-8);
          box-shadow: var(--shadow-md);
        }
      `}</style>
    </div>
  )
}
