# Homebase Redesign Plan

## Current State Assessment

The Homebase dashboard serves as a system monitor (CPU, RAM, disk, uptime), weather widget, todo list, and markdown notes app — plus a services inventory on a second tab. The current implementation has a dark theme with a single accent color, CSS Grid layout, and WebSocket-driven live stats. However, the visual design is utilitarian and lacks the polish expected of a daily-use dashboard.

## Five Biggest Visual Weaknesses

1. **No visual depth or surface hierarchy.** Cards are flat rectangles with identical styling — same background, same border, no shadows, no gradients. In a dark theme, elevation must be communicated through subtle surface layering (lighter backgrounds for higher surfaces, subtle box-shadows, or glow). Currently every card reads as the same flat plane, making the dashboard feel like a wireframe rather than a finished product.

2. **Cards are completely static with zero hover feedback.** The `.card` class (used by CPU, Memory, Disk, Uptime, Weather, Todos, Notes) has no `:hover` state, no cursor change, no border highlight, no subtle lift. Only `.service-card` (on the services tab) has a `transition: border-color 0.2s`. Dashboard cards feel inert — there's no affordance that they're interactive or live.

3. **Typographic hierarchy is nearly invisible.** The h1 title is 1.8rem (reasonable), but all card headings are 0.75rem uppercase in `--muted` gray with 0.08em letter-spacing. Stat values are 1.1rem with font-weight 600. The only standout is the weather temperature at 2.4rem. Everything else — labels, values, buttons, empty states — sits in a narrow 0.75–1.1rem range with similar weight. There's no clear scan path; the eye doesn't know where to land first.

4. **No micro-interactions or meaningful animations.** The entire animation budget consists of: progress bar width transition (1s ease), button opacity (0.15s), and nav tab underline (0.15s). There are no card entrance animations, no staggered loading, no checkmark animation for todos, no pulse for live WebSocket data, no page-switch transitions, no skeleton loaders. The interface feels frozen rather than alive — ironic for a dashboard showing live system stats.

5. **The layout is one uniform grid with no zoning.** Everything lives in a single `auto-fit, minmax(280px, 1fr)` grid. There's no visual grouping between "system metrics" and "personal widgets" (todos, notes, weather). The notes card forces `grid-column: span 1` which creates awkward orphaned columns at certain widths. No sidebar, no header with time/date, no footer. Just `<h1>` + cards. The services tab is a separate page entirely rather than being integrated.

---

## Redesign Plan

### 1. Color System

Move from a flat 2-surface palette to a 3-surface elevation model, add a secondary accent, and introduce semantic tints.

```
Current palette:
  bg:        #0f1117   (page background)
  card-bg:   #1a1d27   (card surface)
  border:    #2a2d3a
  accent:    #6c8cff   (single blue)

Proposed palette:
  --bg:          #090b10   (deepest page background — slightly darker for contrast)
  --surface-1:   #11131a   (low-elevation surface — sidebar, nav bar)
  --surface-2:   #1a1d28   (card surface — same as current card-bg)
  --surface-3:   #222533   (high-elevation surface — modals, hovered cards, tooltips)
  --border:      #252836   (subtle border — slightly lighter for better visibility)
  --border-hover:#3a3f55   (border highlight on hover/focus)
  --text:        #e4e7f0   (primary text)
  --muted:       #7c81a0   (secondary text — more purple-leaning for warmth)
  --accent:      #6c8cff   (primary accent — keep the blue)
  --accent-2:    #a78bfa   (secondary accent — violet, for weather/notes distinction)
  --green:       #4ade80   (success / low usage)
  --yellow:      #fbbf24   (warning / medium usage — warmer than facc15)
  --red:         #f87171   (danger / high usage)
  --orange:      #fb923c   (elevated warning, optional)

Gradient accents:
  --gradient-accent: linear-gradient(135deg, #6c8cff, #a78bfa)
  --gradient-warm:   linear-gradient(135deg, #fb923c, #f87171)
  --gradient-success: linear-gradient(135deg, #4ade80, #34d399)

Background texture:
  body background adds a subtle repeating grid-dot pattern (rgba(255,255,255,0.015) every 20px)
  for a "terminal/control room" feel without being distracting.
```

### 2. Typography

Introduce a clear 5-level scale, use a monospace font for data/metrics, and add weight variation.

```
Font families:
  --font-sans:   'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif
  --font-mono:   'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace

Type scale (using clamp() for fluid sizing):
  --text-xs:     clamp(0.65rem, 0.7vw, 0.75rem)    // card headings, labels
  --text-sm:     clamp(0.8rem, 0.85vw, 0.875rem)   // body, descriptions
  --text-base:   clamp(0.9rem, 0.95vw, 1rem)       // default
  --text-lg:     clamp(1.1rem, 1.5vw, 1.25rem)     // stat values
  --text-xl:     clamp(1.5rem, 2vw, 1.8rem)        // page title
  --text-2xl:    clamp(2rem, 3vw, 2.8rem)          // hero metrics (weather temp)
  --text-3xl:    clamp(2.5rem, 4vw, 3.5rem)        // big numbers

Usage rules:
  - All numeric data (CPU %, RAM GB, uptime) uses `--font-mono` with `font-weight: 500`
  - Card headings use `--font-sans`, uppercase, letter-spacing 0.1em, font-weight 600
  - Page title uses `--font-sans`, weight 800, letter-spacing -0.03em
  - Weather temperature is the only `--text-3xl` element — it becomes the hero stat
  - Labels and metadata use `--text-xs` with `--muted` color
```

### 3. Card Design

Cards need elevation, hover interaction, and semantic differentiation.

**Base card (`--surface-2`)**
```css
.card {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 12px;          /* slightly larger than current 10px */
  padding: 20px;
  min-height: 120px;
  transition: all 0.25s ease;
  position: relative;
  /* Subtle inner highlight at top edge for depth */
  box-shadow: 0 1px 0 rgba(255,255,255,0.03) inset;
}
.card:hover {
  border-color: var(--border-hover);
  background: var(--surface-3);
  box-shadow: 0 2px 0 rgba(108,140,255,0.1) inset;
  transform: translateY(-1px);
  /* Subtle glow */
  box-shadow: 0 4px 24px rgba(108,140,255,0.06), 0 1px 0 rgba(255,255,255,0.04) inset;
}
```

**Metric cards (CPU, RAM, Disk, Uptime)**
- Left accent border: `border-left: 3px solid var(--accent)` — color-coded per metric (CPU=accent, RAM=accent-2, Disk=orange, Uptime=green)
- Progress bars use a subtle gradient fill instead of flat color
- Compact layout with the number as the hero element

**Weather card — special treatment**
- Larger than other cards (span 2 columns on wider screens)
- Background uses a subtle gradient overlay reflecting conditions (cool blue for cold, warm orange for hot)
- Large emoji/icon alongside the temperature
- Temperature uses `--font-mono` at `--text-3xl`

**Todo / Notes cards**
- Todo items get a slide-in animation when added
- Checkbox has a scale + color transition when toggled (currently instant)
- Notes use a subtle left border accent on each item
- Empty state shows a friendly icon + message, not just text

**Service cards (Services tab)**
- Keep the link-card pattern but add icon glow on hover
- Status dot gets a subtle pulse animation when online
- Offline services show a muted/dimmed card with reduced opacity

### 4. Animations

Layer animations in order of entrance, then add micro-interactions.

**Page load sequence (staggered card entrance)**
```css
@keyframes cardEnter {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.card {
  animation: cardEnter 0.4s ease-out both;
}
.card:nth-child(1) { animation-delay: 0.05s; }
.card:nth-child(2) { animation-delay: 0.10s; }
.card:nth-child(3) { animation-delay: 0.15s; }
.card:nth-child(4) { animation-delay: 0.20s; }
.card:nth-child(5) { animation-delay: 0.25s; }
.card:nth-child(6) { animation-delay: 0.30s; }
.card:nth-child(7) { animation-delay: 0.35s; }
```

**Live data pulse**
```css
@keyframes livePulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(108,140,255,0.4); }
  50%      { box-shadow: 0 0 0 4px rgba(108,140,255,0); }
}
.connected-dot {
  animation: livePulse 2s ease-in-out infinite;
}
```

**Progress bar**
- Keep the 1s ease transition but add a subtle shimmer gradient that moves across the bar when it updates
```css
@keyframes shimmer {
  0%   { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
.progress-fill::after {
  content: '';
  position: absolute; inset: 0;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent);
  background-size: 200% 100%;
  animation: shimmer 2s ease-in-out;
}
```

**Todo checkmark**
```css
@keyframes checkPop {
  0%   { transform: scale(0); opacity: 0; }
  60%  { transform: scale(1.3); }
  100% { transform: scale(1); opacity: 1; }
}
.todo-item.completed .todo-check::after {
  animation: checkPop 0.25s ease-out;
}
```

**Page transitions**
```css
@keyframes fadeSlideIn {
  from { opacity: 0; transform: translateX(8px); }
  to   { opacity: 1; transform: translateX(0); }
}
.page.active {
  animation: fadeSlideIn 0.3s ease-out;
}
```

**Delete button reveal**
- Delete buttons stay at opacity 0 and only appear on row hover (desktop) or always visible (touch)
```css
.delete-btn {
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
}
.todo-item:hover .delete-btn,
.note-item:hover .delete-btn {
  opacity: 0.5;
}
```

**Hover lift on all cards**
- All cards get `transform: translateY(-2px)` on hover with shadow deepening
- This is the single most impactful change — it makes the dashboard feel tactile

### 5. Layout Improvements

Restructure the single-grid approach into zoned sections with better information architecture.

**New layout structure:**
```
┌──────────────────────────────────────────────────┐
│  ⬥ Homebase           12:34  Mon, May 11     ⬤  │  ← header bar
├──────────┬───────────────────────────────────────┤
│          │  ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  NAV     │  │  CPU     │ │  RAM    │ │  DISK   │  │  ← system metrics row
│          │  └─────────┘ └─────────┘ └─────────┘  │
│ Dashboard│  ┌──────────────────────┐ ┌─────────┐  │
│ Services │  │     UPTIME           │ │ WEATHER │  │  ← info row
│          │  └──────────────────────┘ └─────────┘  │
│          │  ┌──────────────────────┐ ┌─────────┐  │
│          │  │     TODOS            │ │ NOTES   │  │  ← productivity row
│          │  └──────────────────────┘ └─────────┘  │
├──────────┴───────────────────────────────────────┤
│  Homebase v2 · martin-geile-maschine             │  ← footer
└──────────────────────────────────────────────────┘
```

**Key changes:**

1. **Sidebar navigation instead of tab bar.** Move Dashboard/Services into a slim sidebar (60px collapsed, 200px expanded). This frees vertical space and feels more like a real dashboard app. Icons-only by default with tooltips; click to expand.

2. **Header bar with live clock.** Add the current time (updating every second) and date to the top right. Small quality-of-life touch that makes the dashboard feel alive. Also shows the WebSocket connection indicator.

3. **Zoned card rows.** Group cards into three rows:
   - **System metrics** (CPU, RAM, Disk) — equal-width 3-column grid
   - **Info** (Uptime + Weather side by side) — Uptime takes less space, weather takes more
   - **Productivity** (Todos + Notes side by side) — equal split
   Each row has a subtle section label or just natural whitespace separation.

4. **Responsive breakpoints:**
   - `>1400px`: Sidebar + 3-column metrics, 2-column info, 2-column productivity
   - `900–1400px`: Collapsed sidebar (icons only) + same grid
   - `600–900px`: No sidebar (bottom nav bar), metrics wrap to 2+1, info stacks
   - `<600px`: Single column, bottom nav, all cards full width

5. **Services page redesign.** Instead of a separate "page," integrate services as a collapsible section or a sidebar-persistent panel. If it stays as a page, give it the same card treatment with staggered entrance.

6. **Footer.** Small, muted footer with version and hostname. Grounds the layout.

**CSS Grid refinements:**
```css
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  /* Row 1: CPU, RAM, Disk */
}
.dashboard-grid .info-row {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 16px;
  /* Row 2: Uptime (1fr), Weather (2fr) */
}
.dashboard-grid .productivity-row {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  /* Row 3: Todos, Notes */
}
```

---

## Implementation Notes

- All changes are CSS-only — the HTML structure and JavaScript logic remain unchanged except for the new sidebar markup, header bar, and footer.
- The font stacks use system fonts as fallbacks; Inter and JetBrains Mono are loaded from Google Fonts with `font-display: swap` so the page renders immediately.
- Animation durations are kept under 400ms to feel snappy. The `prefers-reduced-motion` media query disables all animations.
- The proposal maintains the existing WebSocket architecture, API endpoints, and all functionality. This is a visual redesign only.
- Color contrast ratios meet WCAG AA: `--text` (#e4e7f0) on `--surface-2` (#1a1d28) = ~12:1 (passes), `--muted` (#7c81a0) on `--surface-2` = ~4.8:1 (passes for large text, acceptable for UI labels).
