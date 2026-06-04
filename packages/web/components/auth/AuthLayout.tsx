"use client";

import { BookOpen } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

interface AuthLayoutProps {
  title: string;
  subtitle: string;
  footerText: string;
  footerLinkHref: Route;
  footerLinkText: string;
  children: ReactNode;
}

/** Shared layout shell for login and register pages: logo + card + footer link. */
export function AuthLayout({
  title,
  subtitle,
  footerText,
  footerLinkHref,
  footerLinkText,
  children,
}: AuthLayoutProps) {
  return (
    <div className="w-full max-w-sm">
      {/* Logo */}
      <div className="flex justify-center mb-8">
        <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center">
          <BookOpen className="w-5 h-5 text-primary-foreground" />
        </div>
      </div>

      {/* Card */}
      <div className="bg-card border border-border rounded-xl shadow-lg p-8">
        <h1 className="text-xl font-semibold text-foreground text-center mb-1">{title}</h1>
        <p className="text-sm text-muted-foreground text-center mb-6">{subtitle}</p>
        {children}
      </div>

      {/* Footer link */}
      <p className="mt-6 text-center text-sm text-muted-foreground">
        {footerText}{" "}
        <Link
          href={footerLinkHref}
          className="text-primary font-medium hover:text-primary/80 transition-colors no-underline"
        >
          {footerLinkText}
        </Link>
      </p>
    </div>
  );
}
