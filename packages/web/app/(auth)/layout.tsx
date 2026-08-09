import { FormalitySwitcher } from "@/components/auth/FormalitySwitcher";
import { LanguageSwitcher } from "@/components/auth/LanguageSwitcher";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative min-h-screen flex items-center justify-center bg-background p-4">
      {children}
      <div className="absolute bottom-4 right-4 flex items-center gap-2">
        <LanguageSwitcher />
        {/* Hidden for en (renders null) — English has no du/Sie distinction. */}
        <FormalitySwitcher />
      </div>
    </div>
  );
}
