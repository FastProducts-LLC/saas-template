// Class recipes for the marketing design system (DESIGN.md). Every element
// that uses them must sit inside a `.mk` scope (index.css), which provides
// the font, the carbon text color, and the --mk-* derived variables.

export const MK_WRAP = "mx-auto w-full max-w-[1360px] px-6 md:px-10 lg:px-16";
export const MK_MONO = "font-[family-name:var(--font-mono)]";

// Type scale — weight 400 throughout; hierarchy is size + tracking.
export const MK_DISPLAY = "text-[44px] leading-[1.02] tracking-[-0.025em] sm:text-[64px]";
export const MK_H2 = "text-[32px] leading-[1.08] tracking-[-0.02em] sm:text-[48px]";
export const MK_STATEMENT = "text-[26px] leading-[1.18] tracking-[-0.015em] sm:text-[40px]";
export const MK_H3 = "text-2xl leading-tight tracking-[-0.015em]";
export const MK_H4 = "text-xl tracking-[-0.01em]";
export const MK_LEAD = "text-xl leading-snug text-[var(--mk-muted)]";
export const MK_BODY = "text-base leading-relaxed text-[var(--mk-muted)]";
export const MK_EYEBROW_BASE = "text-[11px] uppercase tracking-[0.08em]";
export const MK_EYEBROW = `${MK_EYEBROW_BASE} text-[var(--mk-muted)]`;
export const MK_EYEBROW_DARK = `${MK_EYEBROW_BASE} text-white/60`;
export const MK_INDEX = `${MK_MONO} text-xs tabular-nums text-[var(--mk-muted)]`;
