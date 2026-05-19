/**
 * Body parsing and assembly utilities for KB template sections.
 *
 * Templates define named sections. The entry body stores them as markdown:
 *   ## section_name
 *   Section content here...
 *
 * These utilities parse that format and assemble it back.
 */
import type { KBTemplateSection } from "@/lib/api/kb";

/** Try to parse a body string into named section contents. */
export function parseSectionsFromBody(
  body: string,
  sections: KBTemplateSection[],
): { sectionContents: Record<string, string>; remaining: string } {
  const sectionContents: Record<string, string> = {};
  let remaining = body;

  for (const section of sections) {
    const regex = new RegExp(
      `##\\s*${escapeRegex(section.name)}\\s*\\n([\\s\\S]*?)(?=\\n##\\s|$)`,
      "i",
    );
    const match = remaining.match(regex);
    if (match) {
      sectionContents[section.name] = match[1].trim();
      remaining = remaining.replace(match[0], "").trim();
    } else {
      sectionContents[section.name] = "";
    }
  }

  return { sectionContents, remaining };
}

/** Assemble section contents into a markdown body string. */
export function buildBodyFromSections(
  sections: KBTemplateSection[],
  sectionContents: Record<string, string>,
  extraBody: string,
): string {
  const parts: string[] = [];
  for (const section of sections) {
    const content = sectionContents[section.name]?.trim();
    if (content) {
      parts.push(`## ${section.name}\n${content}`);
    }
  }
  const extra = extraBody.trim();
  if (extra) parts.push(extra);
  return parts.join("\n\n");
}

/** Escape special regex characters in a string. */
function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
