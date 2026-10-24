# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** CryptoPulse
**Revised:** 2026-10-24 (second version: new palette, light theme, landing page)
**Category:** Fintech/Crypto, real-time monitoring dashboard
**Audience:** the project jury and the team during the demo; anyone watching BTC/ETH minute by minute.
**Primary job:** show what the market is doing now and explain why each alert fired.

Accessibility and interaction rules come from ui-ux-pro-max (priority order: accessibility, touch, performance, style, layout, type and colour, motion, forms, navigation, charts).

---

## Principles

1. **One memorable element.** The landing hero is the live BTC price set large, with its last hour drawn underneath. It is the only animation that plays without user action (the line draws once on load). Everything else stays quiet.
2. **Numbers first.** Figures use tabular digits so they do not jump on refresh. Labels are short, in sentence case, never all caps.
3. **Colour has a meaning.** Green and red are reserved for up and down; amber and red markers for warning and critical alerts. Each one is always paired with an arrow, icon or letter.
4. **Structure carries information.** Key figures sit in one strip split by hairlines instead of separate cards. Numbered markers are used only for a real sequence (the data pipeline).
5. **Both themes are first class.** Every colour is a CSS variable defined once per theme. Components never name a colour directly.

---

## Colour

Set by `data-theme` on `<html>`: saved choice (`localStorage` key `cp.theme`), otherwise the system preference. A script in `index.html` applies it before first paint.

| Role | Night (dark) | Day (light) | CSS variable |
|---|---|---|---|
| Page background | `#10141B` graphite | `#F3F5F9` cool paper | `--color-background` |
| Panel | `#171C25` | `#FFFFFF` | `--color-card` |
| Raised / track | `#1F2631` | `#E9EDF4` | `--color-muted` |
| Text | `#EEF1F6` | `#131925` | `--color-foreground` |
| Secondary text | `#9AA3B2` | `#566173` | `--color-muted-foreground` |
| Hairline | `#2A3240` | `#DCE1EA` | `--color-border` |
| Accent (links, active, primary button, price line) | `#93A8FF` periwinkle | `#3450D6` indigo | `--color-primary` |
| Text on accent | `#10141B` | `#FFFFFF` | `--color-on-primary` |
| Up | `#3CCB8E` | `#08774D` | `--color-up` |
| Down / critical | `#FF7070` | `#C62F3B` | `--color-down`, `--color-critical` |
| Warning | `#F5B544` | `#8F5B00` | `--color-warning` |

Chart alert markers keep the same fill in both themes (`--marker-warning #F5B544`, `--marker-critical #FF7070`) with a dark letter (`--marker-text #10141B`).

All text pairs measured at 4.5:1 or more on background, panel and raised surfaces in both themes.

---

## Typography

| Role | Family | Use |
|---|---|---|
| Display | **Bricolage Grotesque** (variable, optical size 96 for large sizes) | Headlines, page titles, the hero price |
| Text and figures | **IBM Plex Sans** 400/500/600, `font-variant-numeric: tabular-nums` for numbers | Everything else |
| Code | **IBM Plex Mono** | Shell commands and run ids only |

Scale: hero 2.5 to 4.25rem (fluid), section titles 1.5 to 2rem, page title 1.75rem, panel title 1.0625rem, body 1rem, secondary 0.875rem, small 0.8125rem, badges 0.75rem. Headlines use tight negative tracking; body line-height 1.5; text blocks kept under about 70 characters.

---

## Layout and spacing

- Landing: left-aligned, max width 1180px. Hero in two columns (pitch, live price panel), then "What you can check" (page list and latest alerts), "How the data moves" (6 numbered steps), "Who built it", footer.
- Dashboard: sidebar 232px with the five pages; top bar with API status, demo badge, UTC/local switch and theme toggle. Under 900px the sidebar becomes a top row; under 640px the pages move to a bottom tab bar.
- Spacing scale: 2, 4, 8, 12, 16, 24, 40, 72px (`--space-xs` to `--space-4xl`).
- Radii: panels 14px, hero price panel 20px, controls 10px, badges fully rounded.
- Shadows: none in the dark theme; one 1px soft shadow on panels in the light theme.

---

## Components

- **Buttons:** 44px minimum height and width. Primary is filled with the accent; secondary is a panel-coloured outline; icon buttons are 44x44 with an `aria-label`.
- **Segmented control:** a track in `--color-muted`; the selected option is a panel-coloured inset button.
- **Stats strip:** one panel, cells separated by hairlines, value in 1.5rem tabular figures.
- **Alerts:** rows with a 3px left rule (amber warning, red critical), severity badge with icon, reason sentence, then observed value, threshold, baseline, window.
- **Notices:** left rule plus tinted background; demo notice uses the accent.
- **Demo badge:** dashed accent outline, text "Demo data".
- **States:** every view has loading (skeleton, `role="status"`), empty (what to do next) and error (what happened, retry).

---

## Motion

- Landing price line draws once on load (1.6s), then the area and last-point dot fade in. Nothing else animates on its own except the loading skeleton.
- Hover and state changes: 180ms colour and background transitions only, no movement.
- `prefers-reduced-motion: reduce` shows the final state immediately.

---

## Avoid

- All-caps labels, eyebrow labels above headings, accenting one word of a headline.
- Rows of identical cards with the same shadow; gradients used as decoration.
- Colour as the only signal; hover-only information.
- Monospace for ordinary figures (use tabular digits instead).
- Emojis as icons (use the inline Lucide icons in `src/components/Icons.jsx`).

---

## Pre-delivery checklist

- [ ] Both themes checked, text contrast 4.5:1 minimum
- [ ] Focus visible on every control
- [ ] Touch targets 44px (inline text links excepted)
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive at 375px, 768px, 1024px, 1440px; no horizontal scroll
- [ ] Nothing hidden behind the sticky header or the bottom tab bar
- [ ] Loading, empty and error states present
