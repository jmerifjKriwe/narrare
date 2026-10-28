// @vitest-environment jsdom
/**
 * The editor's round-trip gate over the whole demo corpus (D12: two
 * serializers, two gates — the kernel suite pins the ENGINE's serializer as a
 * byte fixed point over these same files; this gate pins the EDITOR's).
 *
 * Every demo chapter and knowledge-base body is loaded into a real TipTap
 * instance (StarterKit + @tiptap/markdown, exactly the extensions the
 * shared MarkdownEditor composes) and read back with `getMarkdown()`. The
 * result must equal the input, modulo the differences named in
 * `NAMED_NORMALISATIONS` below — each entry carries what normalises and why
 * the shape is accepted. A drift not produced by that list fails here until
 * it is named and justified; nothing drifts silently into the store.
 *
 * The corpus is read with node:fs relative to the repo root (this file's own
 * URL, resolved — not cwd, which depends on the runner's invocation
 * directory). Frontmatter is stripped the way the interchange engine strips
 * it (the body is everything after the closing `---`, leading blank lines
 * removed); frontmatter never passes through an editor, so it is out of this
 * gate's scope.
 */
import { Editor } from "@tiptap/core";
import { Markdown } from "@tiptap/markdown";
import StarterKit from "@tiptap/starter-kit";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, test } from "vitest";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../../../..");
const demosRoot = join(repoRoot, "app/kernel/interchange/demos");

/** Every demo .md file, as a path relative to the demos root, sorted so the
 *  gate runs (and fails) in a stable order. */
function corpusFiles(): string[] {
  const files: string[] = [];
  for (const slug of readdirSync(demosRoot).sort()) {
    for (const kind of ["chapters", "kb"] as const) {
      for (const name of readdirSync(join(demosRoot, slug, kind)).sort()) {
        files.push(`${slug}/${kind}/${name}`);
      }
    }
  }
  return files;
}

/** The file's body: frontmatter split the way the interchange engine splits
 *  it (`_split_frontmatter`), then leading blank lines dropped. */
function bodyOf(rel: string): string {
  const lines = readFileSync(join(demosRoot, rel), "utf-8").split("\n");
  if (lines[0] !== "---") return lines.join("\n");
  const closing = lines.findIndex((line, index) => index > 0 && line === "---");
  return lines.slice(closing + 1).join("\n").replace(/^[\r\n]+/, "");
}

/**
 * The named normalisations, applied in the order the serializer composes
 * them (per-text encoding first, then block separation, then the final
 * newline). Each entry is a mechanism `@tiptap/markdown@3.31.3` applies to
 * every non-code text node or block boundary — not a per-file patch: the
 * gate stays a gate because only these shapes are excused, and any other
 * difference is a failure. The `apply` is the mechanical form the test holds
 * the editor to; the comment is the justification. A corpus addition that
 * triggers a shape not covered here (a literal `*` or `[` in prose, a code
 * fence, nested lists) turns this gate red on purpose: name it, decide, then
 * extend the list.
 */
const NAMED_NORMALISATIONS: {
  name: string;
  what: string;
  why: string;
  apply: (text: string) => string;
}[] = [
  {
    name: "entity-encoding",
    what: "`&`, `<` and `>` in plain text are written as `&amp;`, `&lt;`, `&gt;`.",
    why: "The serializer encodes HTML-significant characters so a literal can never render as markup after the next Markdown→HTML pass. The encoding parses back to the bare character, so the document's meaning — and everything the reader sees — is unchanged; only the stored bytes differ, once, after which the shape is stable under further edits. The corpus carries exactly one such character (`&` in one knowledge-base heading).",
    apply: (text) => text.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;"),
  },
  {
    name: "escaped-underscores",
    what: "A literal `_` in plain text is written as `\\_`.",
    why: "The serializer backslash-escapes markdown-significant punctuation in plain text so an underscore that is prose (a field name like `word_count`) can never be re-read as emphasis. The escape parses back to the literal character, so content is unchanged. The corpus carries underscores only as literal text (field-name headings such as `## word_count`), never as `_emphasis_` markup — the serializer writes real emphasis as `*emphasis*`, which stays untouched.",
    apply: (text) => text.replaceAll("_", "\\_"),
  },
  {
    name: "loose-list-tightened",
    what: "A blank line between two items of one list is dropped (the list is written tight).",
    why: "CommonMark calls a list with blank lines between items loose; TipTap's list model has no loose/tight distinction — items are siblings in one list node — and the serializer writes them tight. Content identical: same items, same order, same words; only the spacing convention of the source changes. The corpus's knowledge bases carry a few of these loose lists (imported v1 prose).",
    apply: (text) =>
      text
        .replace(/^(- [^\n]*)\n\n(?=- |\d+\. )/gm, "$1\n")
        .replace(/^(\d+\. [^\n]*)\n\n(?=- |\d+\. )/gm, "$1\n"),
  },
  {
    name: "lazy-list-separated",
    what: "A blank line is inserted between a paragraph and a list that directly follows it.",
    why: "CommonMark lets a list item interrupt a paragraph, so the corpus's `text:` line immediately followed by `- item` parses as paragraph plus list. The serializer writes blocks separated by blank lines — the list is simply a sibling block, and the blank line is the canonical spelling of exactly that structure. Content identical; the source becomes unambiguous (no lazy continuation).",
    apply: (text) =>
      // A line that is neither a heading, a thematic break nor a list item
      // itself, immediately followed by a list line, gains the blank line.
      // (A `#`/`-` first line, or an ordered item, already belongs to a
      // block that ends before the next line.)
      text.replace(/^(?![#-]|\d+\. )([^\n]+)\n(- |\d+\. )/gm, "$1\n\n$2"),
  },
  {
    name: "single-eof-newline-dropped",
    what: "One trailing newline at the end of the body is not emitted.",
    why: "The serializer emits blocks separated by blank lines and no EOF newline; the corpus's single trailing newline (one per file, the interchange format's own spelling) has no block of its own to survive into. Blank lines beyond the first are preserved by the serializer and not touched here.",
    apply: (text) => text.replace(/\n$/, ""),
  },
];

/** The input as the named normalisations spell it — the exact bytes the
 *  gate accepts the editor to emit for this body. */
function normalised(body: string): string {
  return NAMED_NORMALISATIONS.reduce((text, normalisation) => normalisation.apply(text), body);
}

describe("the editor's Markdown round trip over the demo corpus", () => {
  test.each(corpusFiles())("editor round-trips %s without unexplained drift", (rel) => {
    const body = bodyOf(rel);
    const editor = new Editor({
      extensions: [StarterKit, Markdown],
      content: body,
      contentType: "markdown",
    });
    const once = editor.getMarkdown();
    expect(once).toEqual(normalised(body));

    // The output is a fixed point of the editor: what a save writes, the
    // next open reads back unchanged — an edited chapter does not drift
    // further with every pass.
    const second = new Editor({
      extensions: [StarterKit, Markdown],
      content: once,
      contentType: "markdown",
    }).getMarkdown();
    expect(second).toEqual(once);

    editor.destroy();
  });
});
