"use client";

/**
 * A count that eases to its new value when it changes (COMPONENTS.md: the `animated-number` role).
 * Written on `motion/react`, the app's one animation library, rather than installed.
 * - Never animates on first render: a page load shows the real number at once.
 * - Reduced motion: the new number appears immediately.
 * - The DOM always holds the final number for assistive tech (`aria-hidden` on the moving copy).
 */
import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "motion/react";
import { useEffect } from "react";

export function AnimatedNumber({ value, className }: { value: number; className?: string }) {
  const reduce = useReducedMotion();
  // A motion value, rendered as the text itself: no React state changes per frame.
  const current = useMotionValue(value);
  const rounded = useTransform(current, (latest) => Math.round(latest));

  useEffect(() => {
    if (current.get() === value) return;
    if (reduce) {
      current.set(value);
      return;
    }
    const controls = animate(current, value, { duration: 0.28, ease: [0.16, 1, 0.3, 1] });
    return () => controls.stop();
  }, [value, reduce, current]);

  return (
    <span className={className}>
      <motion.span aria-hidden>{rounded}</motion.span>
      <span className="sr-only">{value}</span>
    </span>
  );
}
