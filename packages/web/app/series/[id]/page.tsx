import { use } from "react";

export default function SeriesWorkspacePage({ params }: { params: Promise<{ id: string }> }) {
  use(params); // consume params promise for Next.js 16
  return null; // placeholder — replaced by Task 4.6 (SeriesWorkspace)
}
