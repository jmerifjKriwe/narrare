import { announce as announceToLiveRegion } from "@react-aria/live-announcer";

/**
 * The one door for screen-reader announcements. The shell owns the
 * live-region policy — every caller, whatever capability it lives in,
 * gets the same region and the same politeness — so a component announces
 * without knowing how it is heard.
 */
export function announce(text: string): void {
  announceToLiveRegion(text, "polite");
}
