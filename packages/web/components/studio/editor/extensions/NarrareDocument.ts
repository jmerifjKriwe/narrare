/**
 * NarrareDocument — custom TipTap Document node.
 *
 * Establishes the narrative document schema (content: block+).
 * Replaces StarterKit's default document to provide an extension point
 * for future document-level behavior (chapter metadata, validation, etc.).
 */

import { Node } from "@tiptap/core";

export const NarrareDocument = Node.create({
  name: "doc",
  topNode: true,

  content: "block+",
});
