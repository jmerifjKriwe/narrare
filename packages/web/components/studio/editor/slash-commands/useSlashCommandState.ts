"use client";

/**
 * useSlashCommandState (CR-AUFG-07-20).
 *
 * Bridges a TipTap editor and {@link SlashCommandMenu}. It subscribes to editor
 * transactions, runs the pure {@link parseSlashInput} detector, and exposes the
 * controlled state the menu needs. On selection it deletes the `/query` text
 * (leaving no stray prose) and routes to the dispatch context.
 *
 * Conflict guarantees (spec §43):
 *  - The hook only *reacts* to document text; it binds no key handlers, so it
 *    cannot steal TipTap shortcuts. The menu component eats nav/selection keys
 *    only while mounted (open).
 *  - Escape / typing a space simply closes the menu; the `/` stays as prose.
 */
import type { Editor } from "@tiptap/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { AISlashCommandDefinition, SlashCommandDispatchContext } from "./contracts";
import { buildMenuItems, clampActiveIndex } from "./menu-items";
import type { SlashCommandMenuItem } from "./SlashCommandMenu";
import { resolveSlashState } from "./slash-state";

type Translator = (key: string, params?: Record<string, unknown>) => string;

export interface UseSlashCommandStateParams {
  readonly editor: Editor | null;
  readonly commands: readonly AISlashCommandDefinition[];
  readonly dispatchContext: SlashCommandDispatchContext;
  /** operation_ids the host wired handlers for (others render unavailable). */
  readonly wiredOps: ReadonlySet<string>;
  readonly t: Translator;
}

export interface SlashCommandState {
  readonly open: boolean;
  readonly items: SlashCommandMenuItem[];
  readonly activeIndex: number;
  readonly query: string;
  readonly position: { top: number; left: number };
  readonly setActiveIndex: (index: number) => void;
  readonly selectIndex: (index: number) => void;
  readonly dismiss: () => void;
}

const CLOSED_POSITION = { top: 0, left: 0 };

export function useSlashCommandState({
  editor,
  commands,
  dispatchContext,
  wiredOps,
  t,
}: UseSlashCommandStateParams): SlashCommandState {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndexRaw] = useState(0);
  const [position, setPosition] = useState(CLOSED_POSITION);
  const [hasSelection, setHasSelection] = useState(false);

  // Keep the transaction listener reading the latest inputs without resubscribing.
  const inputsRef = useRef({ commands, dispatchContext, wiredOps, t });
  inputsRef.current = { commands, dispatchContext, wiredOps, t };

  const slashPosRef = useRef<number | null>(null);

  const recompute = useCallback((ed: Editor) => {
    const resolved = resolveSlashState(ed);
    setHasSelection(resolved.hasSelection);
    if (!resolved.open) {
      slashPosRef.current = null;
      setOpen(false);
      return;
    }
    slashPosRef.current = resolved.slashPos;
    setPosition(resolved.position);
    setQuery(resolved.query);
    setOpen(true);
  }, []);

  useEffect(() => {
    if (!editor) return;
    const handler = () => recompute(editor);
    editor.on("transaction", handler);
    editor.on("update", handler);
    return () => {
      editor.off("transaction", handler);
      editor.off("update", handler);
    };
  }, [editor, recompute]);

  // Rebuild the filtered items whenever inputs that affect them change.
  const items = useMemo(
    () => buildMenuItems(commands, query, t, hasSelection, wiredOps),
    [commands, query, t, hasSelection, wiredOps],
  );

  // Keep the active index valid as the list shrinks/grows.
  useEffect(() => {
    setActiveIndexRaw((idx) => clampActiveIndex(idx, items.length));
  }, [items.length]);

  const setActiveIndex = useCallback(
    (index: number) => setActiveIndexRaw(clampActiveIndex(index, items.length)),
    [items.length],
  );

  const dismiss = useCallback(() => {
    setOpen(false);
    setActiveIndexRaw(0);
  }, []);

  const selectIndex = useCallback(
    (index: number) => {
      const item = items[index];
      if (!item || item.availability !== "available") return;
      const ed = editor;
      const slashPos = slashPosRef.current;
      // Remove the `/query` so dispatching does not leave stray command text.
      if (ed && !ed.isDestroyed && slashPos !== null) {
        const caret = ed.state.selection.to;
        if (caret > slashPos) {
          ed.chain().focus().deleteRange({ from: slashPos, to: caret }).run();
        }
      }
      setOpen(false);
      setActiveIndexRaw(0);
      const cmd = inputsRef.current.commands.find((c) => c.id === item.id);
      cmd?.dispatch(inputsRef.current.dispatchContext);
    },
    [editor, items],
  );

  return { open, items, activeIndex, query, position, setActiveIndex, selectIndex, dismiss };
}
