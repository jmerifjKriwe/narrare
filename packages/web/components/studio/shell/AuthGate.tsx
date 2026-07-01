"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import { authApi } from "@/lib/api/client";

interface AuthGateProps {
  children: React.ReactNode;
  loadingLabelKey?: string;
}

export function AuthGate({ children, loadingLabelKey = "appName" }: AuthGateProps) {
  const t = useTranslations("studio.sidebar");
  const router = useRouter();
  const { isError, isLoading } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: authApi.me,
    retry: false,
  });

  useEffect(() => {
    if (isError) router.push("/login");
  }, [isError, router]);

  if (isLoading || isError) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-center flex flex-col items-center gap-4">
          <Image src="/logo.png" alt="" width={48} height={48} className="animate-pulse" priority />
          <span className="sr-only">{t(loadingLabelKey)}</span>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
