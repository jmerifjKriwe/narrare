import type { Metadata } from "next";
import { WizardShell } from "@/components/setup/WizardShell";

export const metadata: Metadata = { title: "Setup" };

export default function WizardPage() {
  return <WizardShell />;
}
