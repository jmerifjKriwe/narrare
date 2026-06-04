export interface MentionAutocompleteResult {
  id: string;
  name: string;
  entity_type: string;
  slug: string;
}

export interface CursorPosition {
  top: number;
  left: number;
}

const MENTION_BODY_PATTERN = /^[A-Za-zÀ-ÖØ-öø-ÿ\s'-]+/;
const MENTION_START_PATTERN = /^[A-Za-zÀ-ÖØ-öø-ÿ]/;

/** Extract @mention query from cursor position. */
export function extractMentionQuery(text: string, cursor: number): string | null {
  const beforeCursor = text.slice(0, cursor);
  const atIndex = beforeCursor.lastIndexOf("@");
  if (atIndex === -1) return null;

  if (atIndex > 0 && /\w/.test(beforeCursor[atIndex - 1])) return null;

  const afterAt = beforeCursor.slice(atIndex + 1);
  if (!afterAt || !MENTION_START_PATTERN.test(afterAt)) return null;

  const match = afterAt.match(MENTION_BODY_PATTERN);
  if (!match) return null;

  const query = match[0];
  if (query.length < 2) return null;

  return query;
}

export function getMentionTextLength(textBeforeCursor: string): number | null {
  const atIndex = textBeforeCursor.lastIndexOf("@");
  if (atIndex === -1) return null;

  const afterAt = textBeforeCursor.slice(atIndex + 1);
  const match = afterAt.match(MENTION_BODY_PATTERN);
  return match?.[0].length ?? null;
}

export function calculateAutocompletePosition(
  text: string,
  cursor: number,
  textareaWidth: number,
): CursorPosition {
  const textBefore = text.slice(0, cursor);
  const lines = textBefore.split("\n");
  const lineHeight = 22;
  const charWidth = 8.5;
  const currentLine = lines.length - 1;
  const currentCol = lines[currentLine]?.length ?? 0;

  return {
    top: currentLine * lineHeight + lineHeight + 6,
    left: Math.min(currentCol * charWidth, textareaWidth - 280),
  };
}

export function replaceMentionAtCursor(
  text: string,
  cursor: number,
  entryName: string,
): string | null {
  const beforeCursor = text.slice(0, cursor);
  const atIndex = beforeCursor.lastIndexOf("@");
  const mentionLength = getMentionTextLength(beforeCursor);
  if (atIndex === -1 || mentionLength === null) return null;

  const afterMention = text.slice(atIndex + 1 + mentionLength);
  return `${text.slice(0, atIndex)}@${entryName}${afterMention}`;
}

export function getInsertedMentionCursor(
  text: string,
  cursor: number,
  entryName: string,
): number | null {
  const atIndex = text.slice(0, cursor).lastIndexOf("@");
  if (atIndex === -1) return null;

  return atIndex + 1 + entryName.length;
}
