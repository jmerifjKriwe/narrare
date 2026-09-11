/**
 * Scratchpad — /scratchpad (NOTES-001 §7).
 *
 * Server wrapper only; all data + interaction live in the client
 * ScratchpadWorkspace (mirrors the series canon page pattern). Lives in the
 * (studio) group so the AuthGate applies.
 */
import { ScratchpadWorkspace } from "@/components/notes/ScratchpadWorkspace";

export default function ScratchpadPage() {
  return <ScratchpadWorkspace />;
}
