import { announce as announceToLiveRegion, clearAnnouncer } from "@react-aria/live-announcer";

/**
 * The one door for screen-reader announcements. The shell owns the
 * live-region policy — every caller, whatever capability it lives in,
 * gets the same region and the same politeness — so a component announces
 * without knowing how it is heard.
 */
export function announce(text: string): void {
  announceToLiveRegion(text, "polite");
}

/** Empty the live region. The shell owns this too: a test between cases
 *  is a caller like any other, and what the region remembers — and for
 *  how long — is not a caller's decision to make. */
export function clearAnnouncements(): void {
  clearAnnouncer("assertive");
  clearAnnouncer("polite");
}
