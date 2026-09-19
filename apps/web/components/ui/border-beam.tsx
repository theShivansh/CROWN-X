/**
 * A light that travels around a card's border, only while real work runs (COMPONENTS.md: the
 * `border-beam` role). Written here rather than installed: the Vengeance version loops forever and
 * would need adapting anyway, and this is a few lines of CSS (`.border-beam` in globals.css).
 * - Mounted by the caller for the duration of the work only; nothing loops when idle.
 * - Colour from `--color-conflict`. Under `prefers-reduced-motion` it is a still 1px conflict border.
 * - Decorative: `aria-hidden`; the stage text beside it says what is running.
 */
export function BorderBeam({ active }: { active: boolean }) {
  if (!active) return null;
  return <span aria-hidden className="border-beam pointer-events-none absolute inset-0 rounded-[inherit]" />;
}
