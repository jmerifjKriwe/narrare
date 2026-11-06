import { Button, Keyboard, Menu, MenuItem, MenuTrigger, Popover } from "react-aria-components";

import { buttonClass } from "./Button";
import { Icon } from "./icons";

/** One offered action: what it says, the key that chooses it, and what it
 *  does. `shortcut` is a hint beside the label — visible for discovery,
 *  and carried in `aria-keyshortcuts` for assistive tech; it is never
 *  part of the accessible name that names the action. */
export type ActionItem = {
  id: string;
  label: string;
  shortcut?: string;
  onSelect: () => void;
  disabled?: boolean;
};

/**
 * The shell's action menu: a labelled trigger in the button matrix, a
 * tokened popover, React-Aria's whole menu contract — the arrows, the
 * type-ahead, Escape back to the trigger, focus contained while it stands.
 * The actions arrive as data, because a menu is a list of verbs one
 * surface offers on one subject: the runhead's chapter actions (WP6) and
 * the shelf's card actions (Task 13) are the same shape wearing different
 * items.
 *
 * The trigger is RAC's `Button`, not the primitive's — the trigger child
 * must answer the press context `MenuTrigger` provides — painted with the
 * one matrix (`buttonClass`), exactly the dialog trigger's pattern. Items
 * carry the focus treatment once: the `--soft` wash under React-Aria's
 * focus attribute, the house ring only where the focus was drawn by a
 * keyboard (`data-focus-visible`, the GridList row's own convention), so
 * an item can never show two rings.
 *
 * The shortcut's two channels never touch the name: the hint renders in
 * RAC's `Keyboard` — a `<kbd>` whose id React-Aria wires into the item's
 * `aria-describedby`, so a reader hears it with the action — and the same
 * string is set as `aria-keyshortcuts` on the item (React-Aria's prop
 * filter drops arbitrary aria attributes, so the attribute is written on
 * the node the ref hands back). The name is the label alone, said
 * outright: flex children render no whitespace between them, and a
 * content-built name would stitch "Nach obenAlt" into one word.
 */
export function ActionMenu({
  label,
  triggerAriaLabel,
  items,
}: {
  /** The visible label of the trigger. */
  label: string;
  /** The accessible name of the trigger, naming the subject the actions
   *  act on — a row of identical "Actions" words needs the chapter, the
   *  novel, the row to tell one trigger from its siblings. */
  triggerAriaLabel: string;
  items: ActionItem[];
}) {
  return (
    <MenuTrigger>
      <Button
        aria-label={triggerAriaLabel}
        className={`${buttonClass("secondary", "md")} inline-flex items-center gap-1`}
      >
        {label}
        <Icon name="chevronDown" />
      </Button>
      <Popover className="min-w-40 rounded-[var(--radius)] border border-border bg-card p-1 shadow-overlay">
        <Menu className="flex flex-col outline-hidden">
          {items.map((item) => (
            <MenuItem
              key={item.id}
              onAction={() => item.onSelect()}
              isDisabled={item.disabled}
              aria-label={item.label}
              ref={(element) => {
                if (element !== null && item.shortcut !== undefined) {
                  element.setAttribute("aria-keyshortcuts", item.shortcut);
                }
              }}
              className="flex items-center justify-between gap-4 rounded-[var(--radius)] px-2 py-1 text-body outline-hidden data-[focused]:bg-soft data-focus-visible:ring-2 data-focus-visible:ring-focus"
            >
              <span>{item.label}</span>
              {item.shortcut !== undefined ? (
                <Keyboard className="text-meta text-muted">{item.shortcut}</Keyboard>
              ) : null}
            </MenuItem>
          ))}
        </Menu>
      </Popover>
    </MenuTrigger>
  );
}
