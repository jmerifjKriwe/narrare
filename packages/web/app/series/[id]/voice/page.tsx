/**
 * Voice tab — /series/[id]/voice (Spec 3, Tasks 5–6).
 *
 * Activated in Spec 3: renders the functional Series Voice panel (profile a
 * band, view the profile, set a manual override, clear). Previously a disabled
 * placeholder; the tab is now navigable via SeriesTabNav.
 */
import { use } from "react";
import { SeriesVoicePanel } from "@/components/series/SeriesVoicePanel";

export default function VoiceTabPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <SeriesVoicePanel seriesId={id} />;
}
