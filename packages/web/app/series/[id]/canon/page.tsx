/**
 * Canon KB tab — /series/[id]/canon (Spec 1, Slice 5, Task 5.5).
 *
 * Renders the Series-Canon Knowledge Base editor (CanonKBTab). This server
 * component only resolves the route `id`; all data + interaction live in the
 * client component (useCanonKB + CRUD hooks).
 */
import { CanonKBTab } from "@/components/series/CanonKBTab";

interface CanonTabPageProps {
  readonly params: Promise<{ id: string }>;
}

export default async function CanonTabPage({ params }: CanonTabPageProps) {
  const { id } = await params;
  return <CanonKBTab seriesId={id} />;
}
