/**
 * The callers' path for screen-reader announcements — the one door the
 * shell owns (same region, same politeness, whoever calls). The React-Aria
 * dependency itself lives behind `web/ui/`, the only import point; this
 * module only forwards, so a capability's import path does not change when
 * the implementation moves.
 */
export { announce, clearAnnouncements } from "../ui/liveAnnounce";
