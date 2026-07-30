/**
 * Shared layout for /series/[id]/* routes (Spec 1, Slice 4, Task 4.6).
 *
 * Extracts the route `id` and renders the persistent `SeriesWorkspace` shell
 * (hero + tabs) around the matched route page (`children`). The workspace is a
 * client component that owns the data fetch (useSeries) and tab interaction;
 * this server layout only resolves the param and delegates.
 */
import type { ReactNode } from "react";
import { SeriesWorkspace } from "@/components/series/SeriesWorkspace";

interface SeriesLayoutProps {
  readonly children: ReactNode;
  readonly params: Promise<{ id: string }>;
}

export default async function SeriesLayout({ children, params }: SeriesLayoutProps) {
  const { id } = await params;
  return <SeriesWorkspace seriesId={id}>{children}</SeriesWorkspace>;
}
