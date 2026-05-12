import type { Metadata } from "next";
import { EditorLayout } from "@/components/editor/EditorLayout";

interface Props {
  params: Promise<{ id: string }>;
}

export const metadata: Metadata = { title: "Editor" };

export default async function EditorPage({ params }: Props) {
  const { id } = await params;
  return <EditorLayout novelId={id} />;
}
