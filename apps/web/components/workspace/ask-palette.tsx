"use client";

/**
 * The Ctrl+K / ⌘K "Ask CROWN" palette (COMPONENTS.md: the `search-modal` role), adapted rather than
 * installed: a native <dialog> (focus stays inside, Esc closes, focus returns to where it was), one
 * input, and one listbox of recent questions and the workspace's conflicts.
 * - Arrow keys move through the options; Enter asks the typed question or picks the option.
 * - No animation: it opens in its final state.
 */
import { ArrowRight, ClockCounterClockwise, GitDiff, MagnifyingGlass } from "@phosphor-icons/react";
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

import type { ConflictGroup } from "@/lib/api";
import { cn } from "@/lib/utils";

type Option =
  | { kind: "ask"; id: string; question: string }
  | { kind: "recent"; id: string; question: string }
  | { kind: "conflict"; id: string; group: ConflictGroup };

export function AskPalette(props: {
  open: boolean;
  recent: string[];
  conflicts: ConflictGroup[];
  onAsk: (question: string) => void;
  onConflict: (group: ConflictGroup) => void;
  onClose: () => void;
}) {
  const { open, recent, conflicts, onAsk, onConflict, onClose } = props;
  const dialog = useRef<HTMLDialogElement>(null);
  const [text, setText] = useState("");
  const [active, setActive] = useState(0);
  const listId = useId();

  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  const needle = text.trim().toLowerCase();
  const options: Option[] = [
    ...(needle ? [{ kind: "ask" as const, id: "ask", question: text.trim() }] : []),
    ...recent
      .filter((q) => !needle || q.toLowerCase().includes(needle))
      .slice(0, 5)
      .map((question, i) => ({ kind: "recent" as const, id: `recent-${i}`, question })),
    ...conflicts
      .filter((g) => !needle || g.label.toLowerCase().includes(needle))
      .map((group) => ({ kind: "conflict" as const, id: `conflict-${group.key}`, group })),
  ];
  const current = Math.min(active, Math.max(options.length - 1, 0));

  function choose(option: Option | undefined) {
    if (!option) return;
    setText("");
    setActive(0);
    if (option.kind === "conflict") onConflict(option.group);
    else onAsk(option.question);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((current + step + options.length) % Math.max(options.length, 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      choose(options[current]);
    }
  }

  const optionId = (option: Option) => `${listId}-${option.id}`;

  return (
    <dialog
      ref={dialog}
      aria-label="Ask CROWN"
      onClose={onClose}
      onClick={(event) => event.target === dialog.current && onClose()}
      className="mx-auto mt-[12vh] w-[min(640px,calc(100vw-2rem))] rounded-lg border border-border-strong bg-surface-2 p-0 text-text backdrop:bg-bg/70"
    >
      <div className="flex items-center gap-2 border-b border-border px-4">
        <MagnifyingGlass className="size-4 shrink-0 text-text-subtle" aria-hidden />
        <input
          autoFocus
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setActive(0);
          }}
          onKeyDown={onKeyDown}
          maxLength={500}
          placeholder="Ask CROWN about these documents"
          aria-label="Question"
          role="combobox"
          aria-expanded={options.length > 0}
          aria-controls={listId}
          aria-activedescendant={options[current] ? optionId(options[current]) : undefined}
          autoComplete="off"
          className="h-12 min-w-0 flex-1 bg-transparent text-base text-text outline-none placeholder:text-text-subtle"
        />
        <kbd className="shrink-0 rounded-sm border border-border px-1.5 py-0.5 font-mono text-xs text-text-subtle">Esc</kbd>
      </div>
      {options.length ? (
        <ul id={listId} role="listbox" aria-label="Suggestions" className="flex max-h-80 flex-col overflow-y-auto p-2">
          {options.map((option, index) => {
            const first = options.findIndex((o) => o.kind === option.kind) === index;
            return (
              <li key={option.id} role="presentation" className="flex flex-col">
                {first && option.kind !== "ask" ? (
                  <p role="presentation" className="px-2 pt-2 pb-1 text-xs text-text-subtle">
                    {option.kind === "recent" ? "Recent questions" : "Conflicts in this workspace"}
                  </p>
                ) : null}
                <div
                  id={optionId(option)}
                  role="option"
                  aria-selected={index === current}
                  onMouseMove={() => setActive(index)}
                  onClick={() => choose(option)}
                  className={cn(
                    "flex min-h-10 cursor-pointer items-center gap-2 rounded-sm px-2 text-sm",
                    index === current ? "bg-surface-3 text-text" : "text-text-muted",
                  )}
                >
                  {option.kind === "ask" ? (
                    <ArrowRight className="size-4 shrink-0 text-accent" aria-hidden />
                  ) : option.kind === "recent" ? (
                    <ClockCounterClockwise className="size-4 shrink-0 text-text-subtle" aria-hidden />
                  ) : (
                    <GitDiff weight="bold" className="size-4 shrink-0 text-conflict" aria-hidden />
                  )}
                  <span className="min-w-0 truncate">
                    {option.kind === "ask"
                      ? `Ask "${option.question}"`
                      : option.kind === "recent"
                        ? option.question
                        : `Timeline for the ${option.group.label} (${option.group.pairs.length} ${option.group.pairs.length === 1 ? "conflict" : "conflicts"})`}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="px-4 py-3 text-sm text-text-muted">Type a question, then press Enter.</p>
      )}
    </dialog>
  );
}
