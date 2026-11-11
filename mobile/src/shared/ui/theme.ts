// Design tokens mirroring DESIGN.md: monochrome ink structure + one signal
// color (teal), hairline rules for structure — never boxes or shadows.

// Colors are generated: edit shared/brand.toml, then run python3 scripts/gen_brand.py.
export { colors } from "./tokens";

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
} as const;

export const type = {
  display: 28,
  title: 20,
  body: 15,
  small: 13,
  micro: 11,
} as const;
