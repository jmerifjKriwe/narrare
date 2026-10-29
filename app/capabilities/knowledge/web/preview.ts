/**
 * The entity card's preview text, display only. The store keeps the
 * serializer's canonical bytes — HTML entities (`&amp;`, `&lt;`, `&gt;`)
 * and backslash-escaped punctuation (`\_`, `\*`, `` \` ``, `\[`, `\]`,
 * `\~`, `\\`) — and the glance must read like the document, not like the
 * storage format. Decoding inverts the serializer's own order (entities
 * first, then the escape), and the stored value is untouched: a pure
 * string in, string out — the card's reading copy, never an edit.
 */
export function previewText(content: string): string {
  return content
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&amp;", "&")
    .replace(/\\([\\`*_\[\]~])/g, "$1");
}
