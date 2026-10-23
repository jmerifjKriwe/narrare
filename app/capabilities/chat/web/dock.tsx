import { ChatPanel } from "./ChatPanel";

/** The workspace dock surface: the same ask/answer flow as the standalone
 * page, mounted beside the editor. The dock's frame (the column, its close
 * button, the tab) belongs to the workspace that renders this route. */
export function ChatDock() {
  return <ChatPanel />;
}
