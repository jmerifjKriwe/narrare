import { ComboBox as RacComboBox, Input, Label, ListBox, ListBoxItem, Popover } from "react-aria-components";

/**
 * The shell's combo box: a labelled input with a matching dropdown — the
 * search-while-you-type primitive. The caller owns the list (it decides
 * what "matching" means and filters the items it passes) and both outcomes
 * of the box: every keystroke is `onChange`, picking a match from the
 * dropdown is `onPick`. React-Aria owns the rest: the label names the
 * input, the popup is a real listbox, and the arrow keys walk it.
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
      <Label className="text-sm font-medium">{label}</Label>
      <Input className="w-full rounded-md border border-border bg-card px-3 py-2 text-base font-normal data-focused:border-primary data-focused:outline-none data-focused:ring-2 data-focused:ring-focus" />
      <Popover className="max-h-60 w-[var(--trigger-width)] overflow-y-auto rounded-md border border-border bg-card p-1 shadow-overlay">
        <ListBox<{ id: string; text: string }> className="outline-none">
          {(item) => (
            <ListBoxItem
              id={item.id}
              textValue={item.text}
              className="cursor-default rounded px-3 py-2 text-sm outline-none data-focused:bg-panel"
            >
              {item.text}
            </ListBoxItem>
          )}
        </ListBox>
      </Popover>
    </RacComboBox>
  );
}
