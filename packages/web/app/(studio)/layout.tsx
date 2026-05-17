"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import { Sidebar } from "@/components/studio/Sidebar";
import { authApi } from "@/lib/api/client";

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  const t = useTranslations("studio.sidebar");
  const router = useRouter();

  const { isError, isLoading } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: authApi.me,
    retry: false,
  });

  // Redirect to login when the /auth/me call fails
  useEffect(() => {
    if (isError) {
      router.push("/login");
    }
  }, [isError, router]);

  // Loading state
  if (isLoading || isError) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-center flex flex-col items-center gap-4">
          <Image src="/logo.png" alt="" width={48} height={48} className="animate-pulse" />
          <span className="sr-only">{t("appName")}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="size-full flex">
      <Sidebar />
      <main className="flex-1 min-h-0 min-w-0">{children}</main>
    </div>
  );
}
