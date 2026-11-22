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
 * separators, the wizard's compact pill) and the draft's DE|EN|FR order —
 * the generated catalog order is the compiler's, not the design's. Its
 * keyboard contract: arrows cycle and wrap, Home/End jump to the ends,
 * Space/Enter select; the move selects and focuses, and the roving
 * tabindex keeps the group one tab stop. The chip face is a menu button
 * (aria-haspopup="menu"): arrows walk the open menu without choosing,
 * Enter/Space/click choose and return focus to the trigger, Escape closes
 * innermost-first, an outside press closes without stealing focus — the
 * quick menu's popover discipline, on the draft's tile-5 geometry.
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
import { catalogs } from "./generated/catalogs";
import { useTranslation } from "./i18n";
import { activeLocale, applyLocale, chosenLocale, subscribeLocale, type Locale } from "./locale";
import { readPreSetupLocale, storePreSetupLocale } from "./preSetupLocale";
import { queryClient } from "./query";
import { Icon } from "../ui/icons";

/** The draft draws DE|EN|FR with DE leading; every face keeps that order. */
const SWITCHER_ORDER: readonly Locale[] = ["de", "en", "fr"];

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

  // The pre-setup mirror, adopted before paint when the row holds no choice
  // yet — a refresh keeps the language, never flashes the browser's own.
  useLayoutEffect(() => {
    if (!preSetup || chosenLocale() !== null) return;
    const mirrored = readPreSetupLocale();
    if (mirrored !== null) applyLocale(mirrored);
  }, [preSetup]);

  /** Apply and persist a choice — the one write every face makes. The
   *  guard is against the STORED answer: choosing the language the row
   *  already holds (or following the browser when it is followed) is no
   *  write, while a null over a stored choice — and a stored choice over
   *  the follow — is the real change the write owes. */
  async function choose(next: Locale | null) {
    if (next === chosenLocale()) return;
    if (preSetup && next === null) return;
    const previous = chosenLocale();
    applyLocale(next);
    // The choice stands in the settings caches at once (#939): a save
    // whose click lands while the write is in flight reads the row's
    // cache at that moment and must see the pending choice, never the
    // pre-switch answer. The reads already in flight are cancelled first
    // (#940) — an older answer landing after the patch would replace the
    // pending choice with pre-choice truth, and the cancellation's own
    // revert writes the pre-fetch state down, so the patch must come
    // after it. The abandoned answers' writes are dropped; the choice's
    // own invalidation refetch follows the write with the fresher truth.
    // A refusal unwinds only up to the newest choice that still stands —
    // a newer pending or landed choice keeps its value everywhere the
    // choice wrote (the caches, the store, the mirror), and refusals that
    // pile up under it unwind together once it falls too. Every exit
    // settles the choice, and the last one to settle restarts the reads
    // owed a fresh answer: those a cancellation abandoned, and every read
    // once a write landed. (The structural 409 below patches
    // nothing: pre-setup the strict entry cannot exist — the row never
    // answered — and the tolerant entry holds no locale.)
    if (queryClient.isFetching({ queryKey: ["settings"] }) > 0) settingsReadsOwed = true;
    void queryClient.cancelQueries({ queryKey: ["settings"] });
    const choice = patchCachedLocale(next, () => {
      applyLocale(previous);
      if (preSetup && previous !== null) storePreSetupLocale(previous);
    });
    if (preSetup && next !== null) storePreSetupLocale(next);
    try {
      const { response } = await client.PATCH("/api/settings", { body: { locale: next } });
      // Setup required: the row cannot hold the choice yet — the mirror
      // stands, so the choice does too.
      if (preSetup && response.status === 409) {
        settleLocaleChoice(choice, true);
        return;
      }
      if (!response.ok) throw new Error(`refused: ${response.status}`);
      if (preSetup) storePreSetupLocale(null);
      settingsReadsOwed = true;
      settleLocaleChoice(choice, true);
    } catch {
      settleLocaleChoice(choice, false);
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
 * any other. Each patch joins the seam's stack of unsettled choices,
 * oldest first, so a refusal can tell which choice is still the newest.
 */
type LocaleChoice = {
  moved: Array<{ key: readonly unknown[]; prior: unknown }>;
  /** Put the store (and the mirror) back to the answer before this choice. */
  restore: () => void;
  state: "pending" | "accepted" | "refused";
};

let localeChoices: LocaleChoice[] = [];

/** Whether the settings reads must restart once the choices settle: a
 *  choice cancelled a read in flight, or a write landed on the row. */
let settingsReadsOwed = false;

function patchCachedLocale(next: Locale | null, restore: () => void): LocaleChoice {
  const moved: LocaleChoice["moved"] = [];
  const patch = (key: readonly unknown[], tolerant: boolean) => {
    const cached = queryClient.getQueryData<{ locale: string | null }>(key);
    if (cached === undefined) return;
    if (tolerant && cached.locale === null) return;
    moved.push({ key, prior: cached });
    queryClient.setQueryData(key, { ...cached, locale: next });
  };
  patch(["settings", "read"], false);
  patch(["settings"], true);
  const choice: LocaleChoice = { moved, restore, state: "pending" };
  localeChoices.push(choice);
  return choice;
}

/** Settle a choice's write. A landed choice stands over every older one —
 *  their answers can no longer surface, so they leave the stack. A refusal
 *  under a newer unsettled or landed choice changes nothing visible yet;
 *  a refusal at the top unwinds every refused choice from the top down,
 *  each snapshot in reverse order, and the lowest one's restore puts the
 *  store back to the answer that now stands: the newest surviving choice,
 *  or the accepted baseline before them all. Order matters over values: a
 *  later choice can re-assert the same locale, so the stack — not
 *  equality — is the "a newer choice stands" predicate. The caches, the
 *  visible language and the mirror move together or not at all. When the
 *  last choice settles, the settings reads restart if a write landed or a
 *  choice cancelled one in flight — a cancelled read stays idle, a first
 *  load on its loading screen, a refetch's other fields stale, until
 *  something asks again. Waiting for the last choice keeps an older
 *  answer from landing over a newer pending choice. */
function settleLocaleChoice(choice: LocaleChoice, accepted: boolean): void {
  choice.state = accepted ? "accepted" : "refused";
  const at = localeChoices.indexOf(choice);
  if (at !== -1 && accepted) {
    localeChoices = localeChoices.slice(at);
  } else if (at !== -1) {
    let lowest: LocaleChoice | null = null;
    while (localeChoices.at(-1)?.state === "refused") {
      const top = localeChoices.pop() as LocaleChoice;
      for (const entry of top.moved) queryClient.setQueryData(entry.key, entry.prior);
      lowest = top;
    }
    lowest?.restore();
  }
  if (localeChoices.some((pending) => pending.state === "pending")) return;
  localeChoices = [];
  if (!settingsReadsOwed) return;
  settingsReadsOwed = false;
  void queryClient.invalidateQueries({ queryKey: ["settings"] });
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
    const span = SWITCHER_ORDER.length;
    let next: number;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (at + 1) % span;
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = (at - 1 + span) % span;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = span - 1;
    else if (event.key === " " || event.key === "Enter") next = at;
    else return;
    event.preventDefault();
    const code = SWITCHER_ORDER[next];
    void choose(code);
    radioRefs.current[code]?.focus();
  }

  return (
    <div role="radiogroup" aria-label={t("shell.language")} className={face.group}>
      {SWITCHER_ORDER.map((code, at) => (
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
            aria-label={catalogs[code]["locale.name"]}
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

  const activeAt = SWITCHER_ORDER.indexOf(locale);

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
    if (open) itemRefs.current[SWITCHER_ORDER[activeAt]]?.focus();
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
    const span = SWITCHER_ORDER.length;
    let next: number;
    if (event.key === "ArrowDown") next = (at + 1) % span;
    else if (event.key === "ArrowUp") next = (at - 1 + span) % span;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = span - 1;
    else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      pick(SWITCHER_ORDER[at]);
      return;
    } else if (event.key === "Tab") {
      // Close and hand focus back to the trigger; the default Tab action
      // then advances from it — the menu never traps the keyboard.
      close(true);
      return;
    } else return;
    event.preventDefault();
    itemRefs.current[SWITCHER_ORDER[next]]?.focus();
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
        aria-label={`${t("shell.language")}: ${locale.toUpperCase()} (${catalogs[locale]["locale.name"]})`}
        onClick={() => setOpen((previous) => !previous)}
        onKeyDown={triggerKey}
        className={`flex items-center gap-1.5 rounded px-2.5 py-1 font-mono text-meta ${
          open
            ? "border-2 border-primary bg-surface-container-lowest text-primary"
            : "border border-border bg-surface-container-lowest text-foreground transition-colors hover:border-outline-variant"
        } ${FOCUS}`}
      >
        <span className="font-bold">
          {locale.toUpperCase()} ({catalogs[locale]["locale.name"]})
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
          {SWITCHER_ORDER.map((code, at) => (
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
              <span>{catalogs[code]["locale.name"]}</span>
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
