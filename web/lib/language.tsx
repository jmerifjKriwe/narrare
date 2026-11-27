/**
 * The one language contract (D17, shelf row 12 / #892): the switcher UI,
 * the keyboard contract and the refusal restore, owned once in the shell.
 *
 * Four doors rode three capability-local copies of this contract — the
 * welcome's and the wizard header's pre-setup radio groups (the mirror
 * stands until the settings row exists), the provisioning step through the
 * header, and the shelf's post-setup row write. The app-wide chrome's
 * language chip is the fifth face (variante A, the light chrome draft's
 * tile 5 — the chip IS the switcher, not a passive indicator): it mounts
 * `LanguageChip` here, and the doors mount `LanguageSwitcher`, so a choice
 * made on any face is the same write, the same keyboard discipline and the
 * same honesty on refusal.
 *
 * The contract itself: a choice applies at once (the page speaks it before
 * the answer lands), then PATCHes the settings row. Before setup the row
 * cannot hold it — the structural 409 keeps the browser mirror
 * (`preSetupLocale.ts`), a landed write clears the mirror (the row is the
 * record from then on), and any other refusal restores the prior choice
 * and its mirror. Post-setup there is no mirror: the row is the record,
 * and every refusal — the 409 included — restores the prior language.
 * Success invalidates the cached settings row so the shell re-adopts the
 * written choice.
 *
 * The radio face keeps the doors' drafted geometry (the welcome's
 * separators, the wizard's compact pill) and the registry's order — the one
 * list the switcher, the settings cards and the manuscript segment read, so
 * no face keeps a code of its own. Its keyboard contract: arrows cycle and
 * wrap, Home/End jump to the ends, Space/Enter select; the move selects and
 * focuses, and the roving tabindex keeps the group one tab stop. The chip
 * face is a menu button (aria-haspopup="menu"): arrows walk the open menu
 * without choosing, Enter/Space/click choose and return focus to the
 * trigger, Escape closes innermost-first, an outside press closes without
 * stealing focus — the quick menu's popover discipline, on the draft's
 * tile-5 geometry.
 */
import {
  Fragment,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type KeyboardEvent,
} from "react";

import { client } from "./api/client";
import { endonyms, localeOrder } from "./generated/catalogs";
import { useTranslation } from "./i18n";
import {
  activateLocale,
  activeLocale,
  applyLocale,
  chosenLocale,
  subscribeLocale,
  targetLocale,
  type Locale,
} from "./locale";
import { readPreSetupLocale, storePreSetupLocale } from "./preSetupLocale";
import { queryClient } from "./query";
import { Icon } from "../ui/icons";

/** The shell's focus ring on every control the contract offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/**
 * The choice and the write, shared by every face. `preSetup` selects the
 * mirror contract (the welcome and the wizard, where the settings row does
 * not exist yet); the chrome's chip and the shelf's retired radio rode the
 * post-setup contract — the row is the record, no mirror.
 *
 * `next: null` is „Dem Browser folgen“ (the settings face's checkbox, W7):
 * the stored choice is dropped, the page turns to the browser's language at
 * once, and the write carries the schema's own null. The mirror contract has
 * no null face — pre-setup the mirror stands for a positive choice, so a
 * null there is a no-op — and a refusal restores the prior stored choice,
 * exactly like a language's refusal does.
 */
export function useLanguageChoice({ preSetup = false }: { preSetup?: boolean } = {}) {
  // Subscribing here is what makes a switch re-render every face at once —
  // one store, so the chip and the radios can never disagree. `chosen` is
  // the stored answer (null = the browser decides): the settings checkbox
  // reads its state off it, off the same store announcements.
  const locale = useSyncExternalStore(subscribeLocale, activeLocale, activeLocale);
  const chosen = useSyncExternalStore(subscribeLocale, chosenLocale, chosenLocale);

  // The pre-setup mirror, adopted when the row holds no choice yet. The boot
  // has already hydrated it before its ready gate opened, so the first paint
  // is the mirror's language; a mount without that boot settles the
  // activation a microtask later.
  useLayoutEffect(() => {
    if (!preSetup || chosenLocale() !== null) return;
    const mirrored = readPreSetupLocale();
    // The mirror is a choice like any other: its catalog is loaded before
    // the language becomes active. The boot has usually hydrated it already,
    // so this resolves from the store without a request.
    if (mirrored !== null) void activateLocale(mirrored);
  }, [preSetup]);

  /** Apply and persist a choice — the one write every face makes. A
   *  language is already selected only when it is both the stored answer
   *  and the one on screen: after the boot's fallback the row can hold
   *  `fr` while the source shows, and a click on Français is a retry, not
   *  a dead click. The follow choice is selected while it is stored and
   *  its browser language is active; a null over a stored choice — and a
   *  stored choice over the follow — is the real change the write owes. */
  async function choose(next: Locale | null) {
    if (next === chosenLocale() && targetLocale(next) === activeLocale()) return;
    if (preSetup && next === null) return;
    const previous = chosenLocale();
    // The language becomes active only once its catalog is here: a failed or
    // superseded load activates nothing, so this choice writes nothing.
    const activated = await activateLocale(next);
    if (!activated) return;
    // The choice stands in the settings caches at once (#939): a save
    // whose click lands while the write is in flight reads the row's
    // cache at that moment and must see the pending choice, never the
    // pre-switch answer. The reads already in flight are cancelled first
    // (#940) — an older answer landing after the patch would replace the
    // pending choice with pre-choice truth, and the cancellation's own
    // revert writes the pre-fetch state down, so the patch must come
    // after it. The abandoned answers' writes are dropped; the choice's
    // own invalidation refetch follows the write with the fresher truth.
    // A refusal unwinds only the patch that is still the seam's last one
    // — a newer choice's value stands everywhere the choice wrote (the
    // caches, the store, the mirror). (The structural 409 below patches
    // nothing: pre-setup the strict entry cannot exist — the row never
    // answered — and the tolerant entry holds no locale.)
    void queryClient.cancelQueries({ queryKey: ["settings"] });
    const generation = patchCachedLocale(next);
    if (preSetup && next !== null) storePreSetupLocale(next);
    try {
      const { response } = await client.PATCH("/api/settings", { body: { locale: next } });
      // Setup required: the row cannot hold the choice yet — the mirror
      // stands, and no settings refetch is owed (the row did not change).
      if (preSetup && response.status === 409) return;
      if (!response.ok) throw new Error(`refused: ${response.status}`);
      if (preSetup) storePreSetupLocale(null);
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    } catch {
      restoreCachedLocale(generation, () => {
        applyLocale(previous);
        if (preSetup && previous !== null) storePreSetupLocale(previous);
      });
    }
  }

  return { locale, chosen, choose };
}

/**
 * The settings cache entries a choice moves at once (#939): the strict
 * `["settings", "read"]` entry whenever it holds a row — both save
 * surfaces (the profile form, the GoalSetter) read it at click time — and
 * the chrome's tolerant `["settings"]` entry when IT carries a locale.
 * Only an entry that holds a row is patched: a choice invents no row (the
 * strict family holds real answers only), and a tolerant entry without a
 * locale — the outage's dressed nulls read exactly like a stored follow —
 * is left for the landed refetch to reconcile. A `null` choice is a real
 * assertion (the row now follows the browser) and moves the entries like
 * any other. Each patch takes the seam's next generation, so a refusal
 * can tell whether its own patch is still the last one written.
 */
let lastLocalePatch: {
  generation: number;
  moved: Array<{ key: readonly unknown[]; prior: unknown }>;
} | null = null;

function patchCachedLocale(next: Locale | null): number {
  const generation = (lastLocalePatch?.generation ?? 0) + 1;
  const moved: Array<{ key: readonly unknown[]; prior: unknown }> = [];
  const patch = (key: readonly unknown[], tolerant: boolean) => {
    const cached = queryClient.getQueryData<{ locale: string | null }>(key);
    if (cached === undefined) return;
    if (tolerant && cached.locale === null) return;
    moved.push({ key, prior: cached });
    queryClient.setQueryData(key, { ...cached, locale: next });
  };
  patch(["settings", "read"], false);
  patch(["settings"], true);
  lastLocalePatch = { generation, moved };
  return generation;
}

/** Undo a patch — but only its OWN (#940's mirror variant): a refusal
 *  whose patch has been superseded by a newer choice's patch must not
 *  restore its snapshot over the newer value. The comparison is by
 *  GENERATION, not by value: a later choice can re-assert the same
 *  locale, and the snapshots' row halves are identical when no refetch
 *  landed in between, so equality alone cannot tell "this request's
 *  write" from "a newer choice that wrote the same thing". The
 *  generation is exactly the "a newer choice stands" predicate. `onOwn`
 *  runs the store's restore under the same guard — the caches, the
 *  visible language and the mirror move together or not at all. */
function restoreCachedLocale(generation: number, onOwn: () => void): void {
  if (lastLocalePatch === null || lastLocalePatch.generation !== generation) return;
  for (const entry of lastLocalePatch.moved) queryClient.setQueryData(entry.key, entry.prior);
  onOwn();
}

/** The radio face's drafted geometries — each door's port, kept verbatim. */
const RADIO_FACES = {
  welcome: {
    group: "flex items-center gap-1 rounded border border-border/60 bg-surface-container px-2 py-1",
    separators: true,
    active: "rounded bg-surface px-1.5 py-0.5 font-bold text-primary shadow-xs",
    inactive: "px-1.5 py-0.5 text-muted transition-colors hover:text-foreground",
  },
  wizard: {
    group: "inline-flex rounded-lg border border-border bg-surface-container-lowest p-0.5 text-meta",
    separators: false,
    active: "rounded bg-surface-container-high px-2 py-0.5 font-semibold text-primary",
    inactive: "rounded px-2 py-0.5 text-muted transition-colors hover:text-foreground",
  },
} as const;

/**
 * The radio-group face — the welcome's and the wizard's switcher, one
 * component where two copies diverged. The variant carries the door's
 * drafted classes; the contract (order, names, keyboard, write) is shared.
 */
export function LanguageSwitcher({
  variant,
  preSetup = false,
}: {
  variant: keyof typeof RADIO_FACES;
  preSetup?: boolean;
}) {
  const t = useTranslation();
  const { locale, choose } = useLanguageChoice({ preSetup });
  const radioRefs = useRef<Partial<Record<Locale, HTMLButtonElement | null>>>({});
  const face = RADIO_FACES[variant];

  /** The radio group's keyboard contract: arrows cycle and wrap, Home/End
   *  jump to the ends, Space/Enter select; the move selects and focuses. */
  function radioKey(event: KeyboardEvent<HTMLButtonElement>, at: number) {
    const span = localeOrder.length;
    let next: number;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (at + 1) % span;
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = (at - 1 + span) % span;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = span - 1;
    else if (event.key === " " || event.key === "Enter") next = at;
    else return;
    event.preventDefault();
    const code = localeOrder[next];
    void choose(code);
    radioRefs.current[code]?.focus();
  }

  return (
    <div role="radiogroup" aria-label={t("shell.language")} className={face.group}>
      {localeOrder.map((code, at) => (
        <Fragment key={code}>
          {face.separators && at > 0 ? (
            <span aria-hidden="true" className="text-outline-variant opacity-40">
              |
            </span>
          ) : null}
          <button
            type="button"
            role="radio"
            // The endonym names the radio for assistive tech — the visible
            // face stays the draft's compact code.
            aria-label={endonyms[code]}
            aria-checked={code === locale}
            tabIndex={code === locale ? 0 : -1}
            ref={(node) => {
              radioRefs.current[code] = node;
            }}
            onKeyDown={(event) => radioKey(event, at)}
            onClick={() => void choose(code)}
            className={`${code === locale ? face.active : face.inactive} ${FOCUS}`}
          >
            {code.toUpperCase()}
          </button>
        </Fragment>
      ))}
    </div>
  );
}

/**
 * The chrome's chip — variante A (D17): the topbar chip is the real
 * switcher, the light chrome draft's tile 5. The closed chip names the
 * active language (code and endonym); opening docks the draft's menu under
 * it, the active row checked. The write is the same post-setup contract
 * the shelf's radio rode — the row is the record, a refusal restores.
 */
export function LanguageChip() {
  const t = useTranslation();
  const { locale, choose } = useLanguageChoice();
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const itemRefs = useRef<Partial<Record<Locale, HTMLButtonElement | null>>>({});

  const activeAt = localeOrder.indexOf(locale);

  const close = useCallback((returnFocus: boolean) => {
    setOpen(false);
    if (returnFocus) triggerRef.current?.focus();
  }, []);

  /** Choose and close — the choice applies at once (the contract), the
   *  menu retires, and focus returns to the trigger that opened it. */
  function pick(code: Locale) {
    void choose(code);
    close(true);
  }

  // While the menu stands: Escape closes innermost-first, an outside press
  // closes without stealing focus — the quick menu's discipline.
  useEffect(() => {
    if (!open) return;
    function onKey(event: globalThis.KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      close(true);
    }
    function onDown(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [open, close]);

  // Opening moves focus to the active row — the draft's checked lead. A
  // choice closes the menu, so the active row only moves while it stands
  // if another face switched the language — the focus follows the check.
  useEffect(() => {
    if (open) itemRefs.current[localeOrder[activeAt]]?.focus();
  }, [open, activeAt]);

  /** The trigger's keyboard: ArrowDown/ArrowUp open the menu; Enter/Space
   *  are the button's own click. */
  function triggerKey(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    setOpen(true);
  }

  /** The menu's keyboard: arrows walk with wrap without choosing, Home/End
   *  jump, Enter/Space choose, Tab closes and advances past the trigger. */
  function itemKey(event: KeyboardEvent<HTMLButtonElement>, at: number) {
    const span = localeOrder.length;
    let next: number;
    if (event.key === "ArrowDown") next = (at + 1) % span;
    else if (event.key === "ArrowUp") next = (at - 1 + span) % span;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = span - 1;
    else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      pick(localeOrder[at]);
      return;
    } else if (event.key === "Tab") {
      // Close and hand focus back to the trigger; the default Tab action
      // then advances from it — the menu never traps the keyboard.
      close(true);
      return;
    } else return;
    event.preventDefault();
    itemRefs.current[localeOrder[next]]?.focus();
  }

  return (
    <div ref={wrapperRef} className="relative">
      <button
        type="button"
        ref={triggerRef}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        // The visible face is part of the name (WCAG 2.5.3): the language
        // word and the chip's own code-and-endonym label.
        aria-label={`${t("shell.language")}: ${locale.toUpperCase()} (${endonyms[locale]})`}
        onClick={() => setOpen((previous) => !previous)}
        onKeyDown={triggerKey}
        className={`flex items-center gap-1.5 rounded px-2.5 py-1 font-mono text-meta ${
          open
            ? "border-2 border-primary bg-surface-container-lowest text-primary"
            : "border border-border bg-surface-container-lowest text-foreground transition-colors hover:border-outline-variant"
        } ${FOCUS}`}
      >
        <span className="font-bold">
          {locale.toUpperCase()} ({endonyms[locale]})
        </span>
        <Icon name={open ? "expandLess" : "chevronDown"} size={16} />
      </button>
      {open && (
        <div
          id={menuId}
          role="menu"
          aria-label={t("shell.language")}
          className="absolute right-0 top-full z-50 mt-1 w-[190px] space-y-1 rounded-lg border border-border bg-surface-container-lowest p-1.5 shadow-overlay"
        >
          {localeOrder.map((code, at) => (
            <button
              key={code}
              type="button"
              role="menuitemradio"
              aria-checked={code === locale}
              ref={(node) => {
                itemRefs.current[code] = node;
              }}
              onKeyDown={(event) => itemKey(event, at)}
              onClick={() => pick(code)}
              className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-label ${
                code === locale
                  ? "bg-primary/10 font-semibold text-primary"
                  : "text-foreground transition-colors hover:bg-surface-container-low"
              } ${FOCUS}`}
            >
              <span>{endonyms[code]}</span>
              {code === locale ? (
                <Icon name="check" size={15} />
              ) : (
                <span className="font-mono text-meta text-muted">{code.toUpperCase()}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
