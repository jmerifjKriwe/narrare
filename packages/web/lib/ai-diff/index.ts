/** CR-AUFG-07-18 — shared AI diff vocabulary. Public surface. */

export { betaReaderGroundedAdapter, isBetaReaderGrounded } from "./adapters/beta-reader";
export { coAuthorChangeAdapter } from "./adapters/coauthor";
export { kbEnhanceFieldAdapter } from "./adapters/kb-enhance";
export { rewriteAdapter } from "./adapters/rewrite";
export type {
  AIDiffMode,
  AIDiffSegment,
  AIDiffSegmentKind,
  AIDiffState,
  AIDiffViewModel,
} from "./contracts";
export { segmentize } from "./segmentize";
