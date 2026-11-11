# Design System — SaaS Template

The single source of truth for visual decisions. Read this before touching any
UI. Deviations need explicit user approval. Re-run a design consultation and
update this file when you rebrand (see docs/customization.md).

**Status (2026-11-10).** The system is **"Carbon & Lime"** and it is live on
every web surface: the marketing pages, the authed app, platform admin, and
auth. Marketing-specific rules come first; what differs inside the app is under
[App surface](#app-surface). The mobile app and transactional emails take the
same palette values from `shared/brand.toml` but have not had a design pass.

- **Tokens:** `[theme.colors]` / `[theme.fonts]` in `shared/brand.toml`,
  generated into `frontend/src/shared/styles/tokens.css`.
- **Components:** `frontend/src/shared/ui/marketing/` (marketing primitives)
  and `frontend/src/shared/ui/shell/` (app navigation); import from each index.
- **Artwork:** `frontend/src/shared/assets/art/`.
- **Living reference:** `/design-system` in development builds
  (`features/design-system/DesignSystemPage.tsx`) renders the real tokens and
  components. If this document and that page disagree, fix one of them.

## Product Context
- **What this is:** A multi-tenant B2B SaaS starter — organizations, billing,
  credits, metered AI actions, API keys — via app UI and API.
- **Who it's for:** Business operations teams (B2B).
- **Space/industry:** Generic B2B SaaS — the default theme aims for an
  institutional, data-dense feel (think Stripe/Linear/Mercury dashboards).
- **Project type:** Authed web app (dashboard, billing, API keys,
  members, settings) + light editorial marketing site.

## Direction

> **Calm, exact, and a little bit bright.** A white page, near-black type set
> at regular weight, one lime accent, warm sand panels, and facts in mono.
> Structure comes from size, space, and hairlines. Flavor comes from one
> series of sculptural black-block artwork and a few quiet motions.

- **Reference:** ramp.com (white canvas, single acid accent, regular-weight
  grotesk, bento panels, dark closing band).
- **Mood:** modern, sleek, clean. Confident without shouting.
- **Carried over from the earlier system:** every fact is mono; hairlines over
  boxes; no decorative color.

## Color

| Token | Value | Role |
|---|---|---|
| `--canvas` | `#ffffff` | Page background |
| `--sand` | `#f4f2f0` | Panels, bento cards, showcase surfaces |
| `--sand-line` | `#e5e2dd` | Panel borders |
| `--carbon` | `#0c0c0b` | Type, dark bands, footer |
| `--carbon-soft` | `#1c1c1b` | Raised surface on carbon |
| `--lime` | `#e4f222` | **The one accent** |
| `--lime-deep` | `#d3e11c` | Lime hover |

Derived inside the `.mk` scope (`index.css`):
`--mk-muted` = carbon 60% (secondary text) · `--mk-hair` = carbon 10%
(hairlines) · `--mk-chip` = carbon 5% (chips, soft buttons).

Rules:
- **Lime is a fill or a dot, never text on a light surface** (it fails
  contrast). Allowed: primary button fill, status dot, an open-state marker,
  one highlighted value on a carbon band. Always carbon text on lime.
- **One lime action per view.** If two things are lime, one of them is wrong.
- On carbon: text is white, secondary is white 60%, hairlines are white 10–15%.
- No teal, no gradients (the hero bloom is the single exception), no tinted
  shadows.

## Typography

- **Sans:** `--font-marketing` — **Inter Variable**, self-hosted via
  `@fontsource-variable/inter`. **Weight 400 everywhere**, headlines and
  buttons included. Hierarchy is size and tracking, never bold.
- **Mono:** `--font-mono` — IBM Plex Mono for every fact: values, indices,
  chips, identifiers, ledger labels. Use `tabular-nums`.

| Recipe (`styles.ts`) | Size / leading / tracking | Use |
|---|---|---|
| `MK_DISPLAY` | 64 (44 mobile) / 1.02 / -0.025em | One per page: the hero headline |
| `MK_H2` | 48 (32) / 1.08 / -0.02em | Section headings |
| `MK_STATEMENT` | 40 (26) / 1.18 / -0.015em | Two-tone statements |
| `MK_H3` | 24 / tight / -0.015em | Card titles |
| `MK_H4` | 20 / -0.01em | Step and phase titles |
| `MK_LEAD` | 20 / snug, muted | Hero subhead |
| `MK_BODY` | 16 / relaxed, muted | Body copy |
| `MK_EYEBROW` | 11 uppercase / +0.08em, muted | Micro-labels |
| `MK_INDEX` | 12 mono, tabular, muted | `01` `02` indices |

- **Two-tone statement:** the lead sentence in carbon, the continuation in
  muted, same size. Use it instead of a heading + paragraph when one idea
  needs room.
- Headlines are short and end with a period when they are sentences.

## Layout, spacing, radius

- **Container:** `MK_WRAP` — 1360px max, gutters 24 / 40 / 64px. Content is
  **left-aligned**; centered text only inside a spotlight band's columns.
- **Rhythm:** sections are 80px (mobile) / 112px (desktop) apart. Base unit
  4px. White space is deliberate here, unlike the dense app.
- **Radius:** 6px small buttons · 8px large buttons, ledgers · 12px panels ·
  16px showcase panels · 4px chips. No pills.
- **Borders over shadows:** 1px `--sand-line` on panels. The only shadow is
  the ledger's `shadow-sm` on sand.
- **Dark bands:** at most two per page (a mid-page spotlight and the closing
  band, which runs into the carbon footer).

## Components (`shared/ui/marketing`)

All of them assume a `.mk` ancestor.

| Component | What it is | Rules |
|---|---|---|
| `MkButton` | `lime` · `soft` · `ghost` · `outline`; sizes `md` (40px) / `lg` (48px) | `lime` is the single primary. `soft` secondary. `ghost` nav-level. `outline` only on carbon. Renders a router link when given `to`. |
| `Eyebrow` | Uppercase micro-label, optional mono `chip` fact | Tones `light` / `strong` / `dark`. Sits above a heading, never alone. |
| `Chip` | Mono fact chip | Names, counts, identifiers. Not a status badge. |
| `Ledger` | White card of label/value rows, values in mono | The signature texture. Shows real or illustrative **product state**, never invented metrics. `live` adds the pulsing lime dot; `tone="dark"` on carbon. |
| `Panel` | Flat bento surface | Tones `sand` / `canvas` / `carbon`; radius `xl` (cards) or `2xl` (showcase). No nested panels of the same tone. |
| `Art` | Series artwork with the right blend mode | `tone="light"` multiplies into the surface; `tone="dark"` lightens into carbon. Decorative (`alt=""`) unless it carries meaning. |
| `Marquee` | Seamless slow ticker | For short mono chips only. Repeat items enough to overflow the viewport. |
| `Reveal` | One fade-up on scroll | Wrap a block, not every line. `index` staggers siblings. |

## Page patterns

In the order the home page uses them:

1. **Header** — full-width white bar, hairline appears on scroll; wordmark,
   text links, ghost "Sign in", lime "Get started".
2. **Hero** — eyebrow with fact chip, `MK_DISPLAY` headline, `MK_LEAD`
   subhead, lime + soft buttons, then a showcase panel: hero artwork over a
   lime bloom with four drifting ledgers.
3. **Ticker** — strong eyebrow + marquee of mono chips between hairlines.
4. **Statement** — two-tone statement with a floating artwork beside it.
5. **Bento features** — 2 wide / 3 thirds / 1 full-width sand panels; each is
   index, title, body, artwork, ledger.
6. **Spotlight band** — carbon; two-tone statement, wide dark artwork, three
   centered columns under it, one lime value.
7. **Steps** — four columns; artwork, carbon hairline, index, title, body.
8. **FAQ** — heading and artwork left, accordion right; the open marker turns
   lime.
9. **Closing band** — carbon; large heading, lime button, dark artwork on the
   right, running into the carbon footer.

## Artwork

One series, and only one. Every piece is a studio still of **matte black
modular blocks with exactly one glossy lime element**.

- **Light pieces:** pure white background, soft contact shadow, three-quarter
  isometric view, generous margins. Placed with `mix-blend-multiply`.
- **Dark pieces:** pure black background, thin rim light, the lime element
  glows. Placed with `mix-blend-lighten`. Used only on carbon bands.
- **Never:** text, letters, numbers, logos, people, a second accent color,
  background gradients, photographic scenes.
- **Concept:** each piece is a literal metaphor for the thing beside it
  (token stacks for credits, a key for API keys, a crate for shipping).

Prompt template (image model: OpenAI via the `gpt_image_mcp` server):

> Minimal premium 3D product-style render on a pure white (#FFFFFF) seamless
> background. **\<the object, in matte black blocks\>**. Exactly one
> **\<element\>** is glossy chartreuse lime-yellow (#E4F222). Three-quarter
> isometric view, soft diffused studio lighting, gentle soft contact shadow
> directly beneath, generous empty white space on all sides, composition
> centered. Restrained, calm, modern fintech aesthetic. Only two colours:
> matte black and that one lime accent. No text, no letters, no logos, no
> people, no gradients in the background.

For dark pieces swap the first sentence for "pure black (#000000) seamless
background", ask for thin soft rim light and a softly glowing lime element.

Processing (so blends are seamless — model backgrounds are `#fefefe`, not
white):

```sh
# light: clip near-white to white, then WebP
ffmpeg -i in.png -vf "colorlevels=rimax=0.94:gimax=0.94:bimax=0.94" lv.png
cwebp -q 82 -resize 1200 800 lv.png -o frontend/src/shared/assets/art/<name>.webp
# dark: clip near-black to black
ffmpeg -i in.png -vf "colorlevels=rimin=0.03:gimin=0.03:bimin=0.03" lv.png
cwebp -q 84 lv.png -o frontend/src/shared/assets/art/<name>.webp
```

Give every `<img>` its intrinsic `width`/`height`; lazy-load everything below
the fold; only the hero piece is `priority`.

## Motion

| Class / component | Behavior | Where |
|---|---|---|
| `gd-hero-in` | Fade up 20px, 0.85s | Hero copy and showcase panel |
| `mk-float` | ±5px vertical drift, 4.5s, desynced by `--i` | Hero ledgers, statement artwork |
| `mk-pulse` | Lime ring pulse, 2.2s | `Ledger live` dot, live status |
| `Reveal` / `mk-reveal` | Fade up 18px once on scroll, 0.7s, staggered by `--i` | Section blocks, cards |
| `mk-marquee` | 38s linear loop, pauses on hover | Ticker |
| hover | Card artwork scales 4%; step artwork lifts 6px; panel border darkens | Bento, steps |
| `gd-press` | Scale 0.97 on press | Buttons |

Every animation is disabled under `prefers-reduced-motion`, and nothing is
left hidden. Easing is `--ease-out-soft`. No parallax, no scroll-jacking, no
autoplaying video.

## Voice and honesty

- Short, concrete headlines. Say what ships.
- **No invented proof:** no fake customer logos, testimonials, or usage
  stats. Ledger and vignette data is illustrative product state and lives in
  `frontend/src/shared/content/marketing.ts` with the rest of the copy.

## Accessibility

- Carbon on canvas/sand and carbon on lime all exceed 4.5:1. Muted text
  (carbon 60%) is for 16px+ body and labels on canvas/sand only.
- Focus: 2px carbon ring with 2px offset on buttons.
- Decorative artwork has empty alt text; the adjacent copy carries meaning.
- The marquee's duplicate track is `aria-hidden`.

## Anti-patterns (hard bans)

- Lime text on a light surface; two lime actions in one view.
- Bold headlines; a second sans family on this surface.
- Colored icon chips, gradient buttons, glassmorphism, drop-shadowed cards.
- Stock photos, illustrations of people, or artwork outside the series.
- Centered hero copy; pill-shaped buttons.
- Invented logos, quotes, or numbers.

## App surface

The authed app (dashboard, billing, admin, auth, community) and the remaining
public pages (pricing, docs, blog, legal) run on the same palette and type as
the marketing surface. They were migrated by changing token **values** in
`shared/brand.toml`, so the older key names survive as roles:

| Key | Value | Role in the app |
|---|---|---|
| `--ink` / `--ink-soft` | `#0c0c0b` / `#1c1c1b` | Text, primary buttons (= carbon) |
| `--slate` | `#6b6a67` | Secondary text |
| `--paper` | `#faf9f7` | Page tint behind white panels; hover fills |
| `--mist` | `#f4f2f0` | Inset fills: table headers, code, active nav (= sand) |
| `--line` | `#e5e2dd` | Hairlines and panel borders (= sand-line) |
| `--teal` / `--teal-deep` | `#1c1c1b` / `#0c0c0b` | **Signal role**, now carbon: links, focus borders and rings, active state |
| `--success` / `--danger` / `--info` | `#1f7a3d` / `#b45309` / `#0369a1` | Record statuses, as thin markers and stamps only |

- **Type:** `--font-display` and `--font-body` are Inter Variable; facts stay
  IBM Plex Mono. The display role (page titles, counter numerals, wordmark)
  renders at **weight 500 with -0.02em tracking** regardless of the utility at
  the call site (`index.css` "Display role"). Never bold. Body UI text may use
  500/600 for labels and buttons.
- **Buttons:** primary = ink fill, white text. Secondary = 1px `--line`
  border, ink text. Destructive = text-first in `--danger`; filled only for
  the final confirmation. Lime buttons belong to the marketing surface.
- **Links** are ink at medium weight; underline on hover.
- **Lime in the app** is rationed to: the active marker in the sidebar, the
  live credit balance chip, and the bloom behind artwork on the sign-in panel
  and pricing hero. Do not add lime fills to tables, stamps, or forms.
- **Artwork** appears where a screen has room and a moment (sign-in panel,
  the credit-balance panel in the billing overview). Other working screens
  stay artwork-free.

### App navigation (`shared/ui/shell`)

`SidebarShell` + `NavGroup` + `NavItem` are the only way to build app chrome.

- **Structure:** wordmark and context switcher at the top; labelled groups in
  the middle; account block at the bottom. The sidebar is pinned on desktop
  and is a drawer under `lg`, opened from a slim top bar; following a link or
  tapping the backdrop closes it.
- **Grouping:** by the question the user is asking, 2–4 items per group, mono
  10px uppercase labels. Workspace app: *Workspace* (Dashboard, Members,
  Community, Settings) · *Billing & usage* (Billing, API keys) · *Resources*
  (SaaS features, API docs). Platform admin: Overview · *Revenue & usage* ·
  *Tenants* · *Content & community* · *Platform* · *Compliance*.
- **Items:** 32px rows, sentence case, optional 16px line icon. Active = sand
  fill, ink text, 3px lime marker on the left edge. Everything else is quiet
  until hovered.
- **Account block:** platform-admin link (superusers), avatar + name + email
  linking to the profile, sign out. No boxed or colored call-outs here.
- A new destination goes into an existing group; add a group only when three
  or more items share a new question.

### App page anatomy (`shared/ui`)

Every authed page is built from the same parts, in this order, at
`max-w-[1200px]`:

1. **`PageHeader`** — 28px display title, one-sentence slate description,
   optional mono `meta` line, actions on the right (the primary one last).
2. **Overview** — either a `CounterStrip` of `Counter`s (rule above and
   below, vertical hairlines, 40px numerals; a counter may be a link) or,
   where the page has a "state" to show (billing), two overview panels side
   by side.
3. **Numbered sections** — `SectionRule` (`01 — Title ────── [action]`),
   48px apart. The optional `action` slot holds a link or a
   `SegmentedControl`.
4. **Main + rail** — list pages put the primary list at 2/3 and the
   secondary task at 1/3 (Members: people | invite form; Dashboard:
   activity | API panel + shortcuts). Stacks under `lg`.

Settings-style pages (org Settings, Profile) use `SettingsList` +
`SettingsSection`: title and one-line explanation on the left third, the
control in a white panel on the right, rows divided by hairlines.
`tone="danger"` for destructive rows.

`Meter` is the one proportion visual: a flat 2px-radius bar on a sand
track, ink fill, ink/30 for a secondary segment (credits on hold). Use it
for balances, seats, key quotas, and relative pack sizes — never as a
decorative progress bar.

### Hard bans (app)
- Multicolored icon chips (teal/orange/blue/purple squares) — **deleted, never reintroduce**
- Uniform white cards with gray borders as the default container
- Bright badge pills / traffic-light verdicts
- Purple gradients, 3-column icon grids, centered dashboard content
- Oversized empty cards with one number floating in them
- Blur box-shadows in the app shell
- `gray-*` / `indigo-*` Tailwind utilities (use the tokens)

### Spacing
- **Base unit:** 4px
- **Density:** compact-comfortable — denser than the current layout; dead
  whitespace is treated as a defect. Table rows 40px, panel padding 20–24px.
- **Scale:** 2xs(2) xs(4) sm(8) md(16) lg(24) xl(32) 2xl(48) 3xl(64)

### Layout
- **Approach:** grid-disciplined app; editorial marketing (unchanged).
- **Grid:** 12-column main workspace; content zones, not stacks of
  interchangeable cards. Fill the viewport width with working surface —
  a dashboard is a desk, not a poster.
- **Max content width:** 1200px app pages; wider for dense tables.
- **Border radius (hierarchical):** 4px default (panels, inputs, buttons) ·
  8px modals/popovers · 9999px reserved for marketing pills. No pill-shaped
  app buttons.

### Component Language

The core of this system. These replace the generic white-card pattern:

- **Panels (replaces Card):** flat surface, 1px `--line` border (or top+bottom
  rules only), 4px radius, **zero box-shadow**. Header row = title + optional
  state + one action, separated by a hairline. Interior sections divided by
  hairlines, not nested cards.
- **Counter blocks (replaces stat cards):** no boxes, no icons. A shared 1px
  rule across the top of the group, then per-counter: large tabular numeral
  (40–56px), sentence-case label beneath in `--slate`, optional mono delta.
  Counters separated by vertical hairlines.
- **Numbered section rules (replaces ALL-CAPS gray labels):** mono index +
  sentence-case Plex Sans 600 title + hairline running to the right edge:
  `02 — Recent activity ─────────`. Sections claim full width.
- **Ledger tables (default list container):** 13px mono values, tabular-nums,
  40px rows, `--mist` header fill, hairline column/row rules, row hover
  reveals actions on the right. Empty states = ghost rows (dotted lines),
  never an illustration in whitespace.
- **Status stamps (replaces badges):** uppercase Plex Mono 11–12px inside a
  1px border, 2px radius, colored by the semantic tokens as border+text —
  `MATCH` `NO RECORD` `NEEDS REVIEW` `ACTIVE` `REVOKED`. Muted, stamped,
  never filled bright pills.
- **Provenance as ornament:** record detail views show source count +
  last-seen inline, mono, muted — `3 sources · upd 2026-04`. Compliance
  metadata is the decoration.
- **Icons:** structural/navigation only, single color (ink or slate,
  ink when active). Never inside colored chips.

### Motion
- **Approach:** intentional — keep the existing `gd-*` library
  (`gd-page-in`, `gd-stagger-item`, `gd-row-in`, `gd-skel`, `gd-scan-line`,
  `gd-pop` for stamps). **Drop in the app shell:** `gd-shine`, `gd-lift`
  (blur-shadow hover), `gd-drift-*` — marketing may keep them.
- **Easing:** `--ease-out-soft` (enter) · ease-in (exit) · ease-in-out (move)
- **Duration:** micro(50–100ms) short(150–250ms) medium(250–400ms) long(400–700ms)
- **Reduced motion:** everything settles instantly (already implemented).

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-09 | Initial design system created | Multi-perspective design review plus research of reference SaaS products (Stripe, Linear, Mercury) |
| 2026-07-09 | Keep ink/paper/teal palette; teal demoted to signal-only | Category research shows monochrome + one accent |
| 2026-07-09 | Manrope → IBM Plex Sans; add IBM Plex Mono data plane | Institutional tone; mono facts are the system's signature differentiator |
| 2026-07-09 | Ink-filled primary buttons | What Stripe/Linear do; teal fills read default-SaaS |
| 2026-07-09 | Muted stamp statuses, no traffic-light pills | Status reads as a quiet fact, not an alarm |
| 2026-07-09 | Declined full "manila Registry" rebrand | Memorable but too opinionated for a starter template |
| 2026-11-09 | Token source moved to shared/brand.toml; tokens.css is generated | Centralize palette and font families across surfaces; design values unchanged |
| 2026-11-10 | Home page + marketing header/footer redesigned in a Ramp-style language (white/carbon/lime, Inter, sand bento) | User-requested: more modern, sleek, clean; scoped to the marketing surface, app theme unchanged |
| 2026-11-10 | Added generated block artwork and scroll/float motion to the home page | User-requested: more visual, more engaging |
| 2026-11-10 | The marketing direction becomes the design system ("Carbon & Lime"); primitives extracted to `shared/ui/marketing`; living reference at `/design-system` | User-requested: liked the new direction and asked to convert it into a design system |
| 2026-11-10 | Whole web app migrated to Carbon & Lime by retheming token values; Syne and IBM Plex Sans dropped for Inter Variable | User-requested redesign of all internal pages; value-only retheme keeps 40 screens consistent without touching call sites |
| 2026-11-10 | App navigation rebuilt on `shared/ui/shell`: grouped sections, lime active marker, pinned on desktop, drawer on mobile | User-requested: better-organized navigation; the old sidebar had no mobile layout |
| 2026-11-10 | App pages share one anatomy: `PageHeader`, counter strip or overview panels, numbered sections, main + rail; settings pages use two-column `SettingsSection` rows | User-requested IA/spacing pass: page widths, header styles, and section patterns had drifted page to page |
| 2026-11-10 | Billing overview gets a current-plan panel beside a sand credit-balance panel with the credits artwork and a `Meter`; plan and pack cards rebuilt | User-requested: make billing more visual and engaging |
