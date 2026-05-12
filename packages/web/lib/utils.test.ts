import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cn,
  debounce,
  estimateReadingTime,
  formatRelativeTime,
  formatWordCount,
  truncate,
} from "./utils";

describe("cn", () => {
  it("should merge multiple class strings", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });
  it("should handle conditional classes (undefined, false)", () => {
    expect(cn("foo", false && "hidden", undefined, "bar")).toBe("foo bar");
  });
  it("should resolve Tailwind conflicts — last wins", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
  });
  it("should return empty string with no inputs", () => {
    expect(cn()).toBe("");
  });
  it("should handle array inputs", () => {
    expect(cn(["px-2", "py-1"])).toBe("px-2 py-1");
  });
});

describe("formatWordCount", () => {
  it('should format 0 as "0"', () => {
    expect(formatWordCount(0)).toBe("0");
  });
  it("should format 1000 with en locale using comma separator", () => {
    expect(formatWordCount(1000, "en")).toBe("1,000");
  });
  it("should format 1000000 with en locale", () => {
    expect(formatWordCount(1_000_000, "en")).toBe("1,000,000");
  });
  it("should use German locale with period separator", () => {
    expect(formatWordCount(1000, "de")).toBe("1.000");
  });
  it("should default to en locale", () => {
    expect(formatWordCount(5000)).toBe("5,000");
  });
});

describe("estimateReadingTime", () => {
  it('should return "< 1 min" for 0 words', () => {
    expect(estimateReadingTime(0)).toBe("< 1 min");
  });
  it('should return "1 min" for 250 words', () => {
    expect(estimateReadingTime(250)).toBe("1 min");
  });
  it('should return "2 min" for 500 words', () => {
    expect(estimateReadingTime(500)).toBe("2 min");
  });
  it('should return "1 min" for 1 word (Math.ceil rounds up)', () => {
    expect(estimateReadingTime(1)).toBe("1 min");
  });
  it('should return "1 min" for 249 words (Math.ceil rounds up)', () => {
    expect(estimateReadingTime(249)).toBe("1 min");
  });
  it('should return "2 min" for 251 words (Math.ceil rounds up)', () => {
    expect(estimateReadingTime(251)).toBe("2 min");
  });
});

describe("debounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("should call fn after delay", () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    debounced();
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("should reset timer on subsequent calls — only last executes", () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    debounced("a");
    vi.advanceTimersByTime(50);
    debounced("b");
    vi.advanceTimersByTime(50);
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(50);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith("b");
  });

  it("should pass arguments to the debounced function", () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 50);
    debounced("hello", "world");
    vi.advanceTimersByTime(50);
    expect(fn).toHaveBeenCalledWith("hello", "world");
  });
});

describe("formatRelativeTime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-12T12:00:00Z"));
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("should show seconds ago for recent dates", () => {
    const result = formatRelativeTime("2026-05-12T11:59:30Z");
    expect(result).toContain("30");
    expect(result).toMatch(/second/i);
  });
  it("should show minutes ago for dates within the hour", () => {
    const result = formatRelativeTime("2026-05-12T11:30:00Z");
    expect(result).toContain("30");
    expect(result).toMatch(/minute/i);
  });
  it("should show hours ago for dates within the day", () => {
    const result = formatRelativeTime("2026-05-12T10:00:00Z");
    expect(result).toContain("2");
    expect(result).toMatch(/hour/i);
  });
  it("should show days ago for dates within the week", () => {
    const result = formatRelativeTime("2026-05-10T12:00:00Z");
    expect(result).toContain("2");
    expect(result).toMatch(/day/i);
  });
  it("should show formatted date for dates older than 7 days", () => {
    const result = formatRelativeTime("2026-04-01T12:00:00Z");
    expect(result).toMatch(/Apr/);
    expect(result).not.toMatch(/ago/i);
  });
  it("should include year for dates older than 365 days", () => {
    expect(formatRelativeTime("2024-06-15T12:00:00Z")).toContain("2024");
  });
  it("should use English locale by default", () => {
    expect(formatRelativeTime("2026-05-12T11:59:00Z")).toMatch(/ago/i);
  });
});

describe("truncate", () => {
  it("should return short text unchanged", () => {
    expect(truncate("hello", 10)).toBe("hello");
  });
  it("should return text at exact limit unchanged", () => {
    expect(truncate("hello", 5)).toBe("hello");
  });
  it("should truncate text over limit with ellipsis", () => {
    expect(truncate("hello world", 8)).toBe("hello w…");
  });
  it("should handle empty string", () => {
    expect(truncate("", 10)).toBe("");
  });
  it("should handle maxLength of 0 with empty string", () => {
    expect(truncate("", 0)).toBe("");
  });
  it("should truncate single character over limit", () => {
    expect(truncate("abc", 2)).toBe("a…");
  });
});
