"use client";

/**
 * A button that opens a panel below it, with the height morphing open (COMPONENTS.md: the
 * `morphing-disclosure` role). Written here on `motion/react` rather than installed, because the
 * upstream version pulls `lucide-react` and `framer-motion`, both of which the checklist removes.
 * - Content is in the DOM and readable when open; closed is closed, with no hidden-until-JS state.
 * - `aria-expanded` and `aria-controls` on a real button; visible focus ring.
 * - Reduced motion: the panel appears and disappears with no animation.
 */
import { CaretDown } from "@phosphor-icons/react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useId, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Disclosure({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const reduce = useReducedMotion();
  const panelId = useId();
  const transition = { duration: reduce ? 0 : 0.28, ease: [0.16, 1, 0.3, 1] as const };
  return (
    <div className="flex flex-col">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex w-fit items-center gap-1.5 rounded-sm text-xs text-text-muted transition-colors duration-(--duration-fast) ease-out hover:text-text focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <CaretDown
          aria-hidden
          className={cn(
            "size-3.5 transition-transform duration-(--duration-base) ease-out motion-reduce:transition-none",
            open && "rotate-180",
          )}
        />
        {label}
      </button>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            id={panelId}
            key="panel"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={transition}
            className="overflow-hidden"
          >
            <div className="pt-2">{children}</div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
