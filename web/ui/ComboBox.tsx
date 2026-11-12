import { ComboBox as RacComboBox, Input, Label, ListBox, ListBoxItem, Popover } from "react-aria-components";

import { controlClass } from "./field";

/**
 * The shell's combo box: a labelled input with a matching dropdown — the
 * search-while-you-type primitive. The caller owns the list (it decides
 * what "matching" means and filters the items it passes) and both outcomes
 * of the box: every keystroke is `onChange`, picking a match from the
 * dropdown is `onPick`. React-Aria owns the rest: the label names the
 * input, the popup is a real listbox, and the arrow keys walk it.
 *
 * Paint rides the system (R49): the label is `text-label`, the control is
 * `controlClass` (the 36 px input contract, pinned beside `buttonClass`),
 * rows and popover read the type scale with token radii — no legacy
 * `text-sm`/`text-base`/`rounded-md` survives here. The ring answers RAC's
 * `data-focused` — a mouse click focuses the input without a keyboard
 * event, and the box must ring in both cases (field's one treatment).
 *
 * `allowsCustomValue` keeps typed text that matches nothing: a search box
 * must not throw the user's words away on blur.
 */
export function ComboBox({
  label,
  value,
  onChange,
  onPick,
  items,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  onPick: (id: string) => void;
  items: { id: string; text: string }[];
}) {
  return (
    <RacComboBox<{ id: string; text: string }>
      inputValue={value}
      onInputChange={onChange}
      onSelectionChange={(key) => {
        if (key !== null) onPick(String(key));
      }}
      allowsCustomValue
      items={items}
      className="flex flex-col gap-1"
    >
      <Label className="text-label font-medium">{label}</Label>
      <Input className={`${controlClass()} w-full data-focused:ring-2 data-focused:ring-focus`} />
      <Popover className="max-h-60 w-[var(--trigger-width)] overflow-y-auto rounded-[var(--radius)] border border-border bg-card p-1 shadow-overlay">
        <ListBox<{ id: string; text: string }> className="outline-none">
          {(item) => (
            <ListBoxItem
              id={item.id}
              textValue={item.text}
              className="cursor-default rounded-[var(--radius)] px-2 py-1.5 text-body outline-none data-focused:bg-panel"
            >
              {item.text}
            </ListBoxItem>
          )}
        </ListBox>
      </Popover>
    </RacComboBox>
  );
}
