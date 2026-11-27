import { preloadCatalogs } from "./catalogs";

// jsdom implements no scrolling, and a dependency calls window.scrollTo while
// a component mounts; without this every call printed jsdom's "Not
// implemented: Window's scrollTo() method". No test under web/ or app/ reads a
// scroll position, so the no-op hides no behaviour. The guard keeps the node
// environment's tests — which have no window — running.
if (typeof window !== "undefined") {
  window.scrollTo = () => {};
}

// Every test reads a language's real catalog through the bed; the store
// starts preloaded so no test accidentally proves the fallback it is not
// testing.
preloadCatalogs();
