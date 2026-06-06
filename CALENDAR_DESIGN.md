# Homebase Premium Calendar Widget — Design Spec

## Inspiration
- **Apple Calendar** — Clean month grid with colored dots, smooth slide-up day panel, today accent circle
- **Google Calendar** — Color-coded events, event density indicators, week numbers, responsive views
- **FullCalendar** — Vanilla JS calendar library patterns for month views with event overlays

## Theme Colors (Homebase Dark Theme)
```
Background:       #0f1117 (page bg)
Card:            #1a1d27 (modal, panel bg)
Surface:          #22262f (hover/row bg)
Border:           #2a2e3a
Text Primary:     #f0f0f0
Text Secondary:   #9496a0
Text Muted:       #5c5e6b
Accent Blue:      #6c9cff (calendar accent, today highlight)
Accent Pink:      #ff6b9d (events color 1)
Accent Orange:    #ff9f43 (events color 2)
Accent Green:     #4ecdc4 (events color 3)
Accent Purple:    #a29bfe (events color 4)
Accent Yellow:    #feca57 (events color 5)
Accent Teal:      #48dbfb (events color 6)
```

## 6 Event Color Presets (matching homebase accent palette)
```javascript
const EVENT_COLORS = [
  { name: 'Blue',   value: '#6c9cff' },
  { name: 'Pink',   value: '#ff6b9d' },
  { name: 'Orange', value: '#ff9f43' },
  { name: 'Green',  value: '#4ecdc4' },
  { name: 'Purple', value: '#a29bfe' },
  { name: 'Yellow', value: '#feca57' },
];
```

## Font Stack
```
font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif
```

## Component Layout

### Month Grid
```
┌──────────────────────────────────────────────────┐
│  ◀  June 2026  ▶  ┃  Today                      │  ← header bar
│  WK │ Mon │ Tue │ Wed │ Thu │ Fri │ Sat │ Sun │   │  ← weekday headers
│  23 │     │     │     │     │     │     │  1  │   │  ← week number on left
│  24 │  2  │  3  │  4  │  5  │  6  │  7  │  8  │   │
│  25 │  9  │ ◉10 │ 11  │ 12  │ 13  │ 14  │ 15  │   │  ← today = glowing circle
│  26 │ 16  │ 17  │ 18  │ 19  │ 20  │ 21  │ 22  │   │
│  27 │ 23  │ 24  │ 25  │ 26  │ 27  │ 28  │ 29  │   │
│  28 │ 30  │     │     │     │     │     │     │   │
└──────────────────────────────────────────────────┘
```

- Week number column: narrow (36px), right-aligned, text-secondary color
- Day cells: equal width, ~90px min, padded
- Today: glowing accent circle (`#6c9cff`) with box-shadow glow (`0 0 12px rgba(108, 156, 255, 0.4)`)
- Current week: subtle background tint `rgba(108, 156, 255, 0.06)`
- Event dots: small circles (6px) horizontal row under day number. Up to 3 dots, then `+N` text
- Day numbers: top-left in cell
- Adjacent month days (padding days): muted text, no interactivity
- Grid: `display: grid; grid-template-columns: 36px repeat(7, 1fr);`

### Month Navigation
- Left/right chevron buttons: `◀` `▶` unicode, 24px, text-secondary (hover: text-primary)
- Month name + year: `font-size: 18px; font-weight: 600;`
- Today button: text-secondary, pill shape, hover accent-blue, jumps to current month
- Smooth slide animation on month change: `transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1)`
  - Next month: slide-in from right
  - Prev month: slide-in from left
  - Implementation: 2 grids side by side, transform translateX

### Day Detail Panel
- Slide-up from bottom: `transform: translateY(0)` from `translateY(100%)`
- Transition: `0.3s cubic-bezier(0.4, 0, 0.2, 1)`
- Backdrop: semi-transparent overlay behind panel
- Panel height: max 50% of viewport, scrollable
- Header: selected date (e.g., "Tuesday, June 10"), close button (×)
- Event cards: each card has color indicator bar (left 3px), time, title, optional description
- Empty state: "No events for this day" in text-muted

### Add Event Modal
- Centered modal with backdrop blur
- Fields: Title (input), Date (date input, pre-filled to selected day), Time (time input), Color (6 radio-colored circles), Description (textarea, optional)
- Color picker: horizontal row of 6 colored circles, click selects, selected has check icon
- Save button: accent-blue bg, white text
- Cancel button: border only, text-secondary
- Modal entrance: `opacity 0→1 + scale 0.95→1, 0.2s`
- Close on backdrop click or Escape key

### Mobile Responsive (≤768px)
- Switch from grid to list view
- Week numbers hidden
- Weekday headers become short: M, T, W, T, F, S, S
- Day cells become list items grouped by week
- Day detail panel becomes full-screen modal
- Add event modal becomes full-screen with safe-area padding

## CSS Animations
```
Month transition:     transform 0.25s cubic-bezier(0.4, 0, 0.2, 1)
Panel slide:          transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.2s
Modal entrance:       opacity 0.2s, transform 0.2s cubic-bezier(0.4, 0, 0.2, 1)
Day hover:            background-color 0.15s ease
Today glow:           box-shadow 0.3s ease
Event dot:            transform scale(0→1) 0.2s ease
```

## API Integration
- `GET /api/calendar/events` — load all events
- `POST /api/calendar/events` — create new event
- `DELETE /api/calendar/events/{id}` — delete event
- `GET /api/calendar/month?year=Y&month=M` — get month grid with events

## JavaScript Architecture (vanilla, no framework)
- Class: `PremiumCalendar` — manages state, rendering, event handling
- State: `{ currentDate: Date, events: [], selectedDay: null, selectedMonth: Date }`
- Methods: `render()`, `renderGrid()`, `navigateMonth(n)`, `openDay(date)`, `closePanel()`, `openAddModal(date)`, `saveEvent(data)` 
- Event delegation on calendar container for click handling
- Fetch wrapper for API calls with error handling
