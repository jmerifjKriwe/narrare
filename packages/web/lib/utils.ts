import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes safely. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** Format a word count with locale-aware thousands separator. */
export function formatWordCount(count: number, locale = "en"): string {
  return count.toLocaleString(locale);
}

/** Estimate reading time from word count (250 wpm average). */
export function estimateReadingTime(wordCount: number): string {
  const minutes = Math.ceil(wordCount / 250);
  if (minutes < 1) return "< 1 min";
  if (minutes === 1) return "1 min";
  return `${minutes} min`;
}

/** Debounce a function. */
// biome-ignore lint/suspicious/noExplicitAny: generic utility requires any for function type inference
export function debounce<T extends (...args: any[]) => any>(
  fn: T,
  delay: number,
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

/** Format a date relative to now (e.g. "2 hours ago"). */
export function formatRelativeTime(dateStr: string, locale = "en"): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });

  if (diffSec < 60) return rtf.format(-diffSec, "second");
  if (diffMin < 60) return rtf.format(-diffMin, "minute");
  if (diffHour < 24) return rtf.format(-diffHour, "hour");
  if (diffDay < 7) return rtf.format(-diffDay, "day");

  return new Intl.DateTimeFormat(locale, {
    month: "short",
    day: "numeric",
    year: diffDay > 365 ? "numeric" : undefined,
  }).format(date);
}

/** Truncate text to a max length with ellipsis. */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1)}…`;
}

/**
 * Convert basic Markdown to HTML for TipTap consumption.
 *
 * TipTap's `setContent()` expects HTML. When the backend stores content as
 * Markdown (e.g. demo/seed data), the raw syntax (`#`, `**`, etc.) would
 * render as plain text. This lightweight converter handles the common cases
 * found in chapter content. If the input already looks like HTML it is
 * returned unchanged.
 */
export function markdownToHtml(md: string): string {
  if (!md) return "";

  // Already HTML — leave it alone
  if (md.trim().startsWith("<")) return md;

  let html = md;

  // Headers: ### → <h3>, ## → <h2>, # → <h1>  (order matters)
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");

  // Bold: **text** → <strong>text</strong>
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  // Italic: *text* (not inside **)
  html = html.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");

  // Split into blocks by double newlines and wrap non-heading blocks in <p>
  const blocks = html.split(/\n\n+/);
  html = blocks
    .map((block) => {
      const trimmed = block.trim();
      if (!trimmed) return "";
      if (trimmed.startsWith("<h")) return trimmed;
      return `<p>${trimmed.replace(/\n/g, "<br>")}</p>`;
    })
    .join("");

  return html;
}
