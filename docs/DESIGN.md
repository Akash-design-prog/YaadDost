# YaadDost design system

One file that says how YaadDost looks, so every screen is consistent. The tokens below are implemented in
`frontend/css/tokens.css`; if the two disagree, fix the CSS to match this file (or change both on purpose).

## Product context
- **What:** a revision tool. A student pastes notes; Gemma writes flashcards; a second Gemma pass checks every card against the
  notes; a spaced-repetition scheduler (SM-2) brings each card back just before it would be forgotten.
- **Who:** a student revising before exams, often on a phone, often mixing Hindi and English (Hinglish, Roman script).
- **Promise:** your notes stay with a Gemma server you control; every card is checked against what you actually wrote.
- **Tone:** a friend who revises with you. Warm and direct, never cute, never pushy.

## Page type: live surface
The app is the product from the first screen. There is no marketing hero, no scroll cinema, no section counters.
The first screen is today's review (or a clear empty state). Adding notes is a real input at the end of the page, not a
call-to-action button. All data on screen is real: the forgetting-curve strip draws the real SM-2 schedule.

## Signature move: the forgetting-curve strip
A thin timeline of the next 30 days. Every card is a dot on the day it is due; dots stack vertically on the same day.
Grading a card makes its dot hop to its new date. It explains spaced repetition without words and shows progress at a glance.
Overdue cards sit on "today" in marigold. It has a text alternative and is never the only way to read the schedule.

## Colour: six roles, one accent
| Role | Light | Dark | Use |
|---|---|---|---|
| canvas | `#F3F2EE` | `#2B3047` | page ground |
| surface | `#FBFAF7` | `#353B56` | cards, panels, inputs |
| sunk | `#E9E7E0` | `#232739` | pressed, wells, track |
| ink | `#1C1E2B` | `#EEECF7` | text (never pure black or white) |
| ink-soft | `#565B70` | `#BCC0D6` | secondary text (tinted, never flat grey) |
| accent | `#3340C4` | `#A8B2FF` | the one action colour: primary buttons, links, focus, selection |
| accent-ink | `#FFFFFF` | `#12152B` | text on accent |
| edge | `#7E7C8C` | `#959AB8` | borders of controls (needs 3:1) |
| line | `#DAD7CE` | `#424963` | decorative hairlines only |
| due | `#BD7400` | `#F2B53F` | "due today" dots and chips only |
| good / bad | `#1C7A4B` / `#B3261E` | `#7AE0B0` / `#FFA49B` | feedback only |

Rules: one accent for the whole product; marigold means "due" and nothing else; no gradients, no neon, no purple, no cream-and-brass.
Measured contrast: text 4.5:1 or more, controls and focus rings 3:1 or more, checked in the browser tests for both themes.

### Light and dark theme
- Dark is a **soft dusk slate, not black**: the canvas is `#2B3047` (about four times lighter than a typical near-black), and a
  test fails if it drifts too dark or too light. Text stays easy to read (about 11:1) but is gentler.
- Dark is its own token set, not an inversion: surfaces get lighter with elevation, the accent lightens, borders have their own values.
- A moon button in the header switches themes. A saved choice wins; with no choice the page follows the system setting, including
  live changes. `js/theme-init.js` is a small blocking script in `<head>`, so the right theme is on screen from the first frame (no flash).
- The browser's address bar colour (`theme-color`) follows the canvas.

## Type: two families, self-hosted
- **Display:** Bricolage Grotesque (headings, the wordmark, card questions, big numbers). Tracking tightens as size grows.
- **Text:** DM Sans (everything else). Both are SIL Open Font License, files in `frontend/fonts/`.
- Body is 17px at 1.55 line height, measure capped near 62ch. Headings use `text-wrap: balance`, paragraphs `pretty`.
- Scale (rem): 0.8125 / 0.9375 / 1.0625 / 1.25 / 1.625 / 2.25. Weights 400, 500, 600, 700 only. Never uppercase body text.
- Numbers (due counts, intervals) use tabular figures.

## Space, radius, depth
- 4px base: 4, 8, 12, 16, 24, 32, 48, 64. More space above a heading than below it. Group by proximity before adding borders.
- Radius scale is **8, 12, 16 and pill**. Nothing else. Pills only for chips and the pill-shaped toggles.
- Depth is a hairline plus a tint, not shadow. One soft shadow exists, for raised surfaces on hover. No nested cards.
- Layout: single column up to 720px, 16px gutters on phones, 24px from 640px. Targets are at least 44px.

## Motion
- Tokens: instant 80ms, fast 140ms, base 200ms, slow 320ms. Entrances ease-out `cubic-bezier(0.23,1,0.32,1)`.
- Animate only `transform` and `opacity` (and `clip-path` for wipes). Never `transition: all`, never `scale(0)`.
- Press: `scale(0.97)`. Enter from `scale(0.97)` plus opacity. Hover motion only on `(hover: hover) and (pointer: fine)`.
- The peak is the grade moment: the dot hops, the card settles, a quiet tint confirms. The ending is "all caught up".
- Reduced motion means gentler, not none: keep opacity and colour changes, drop movement.

## Components and their states
Every interactive control defines: default, hover, focus-visible, active, disabled, loading, error, empty.
- **Button:** primary (accent fill), secondary (surface plus edge border), quiet (text only). Labels are verb + object.
- **Grade buttons:** Bhool gaya (again), Mushkil (hard), Yaad tha (good), Aasaan (easy). Keys 1 to 4. Quiet colours; the feedback is the dot.
- **Card:** question in display type, answer revealed below. A small "Checked against your notes" mark appears only when the
  Verifier ran; offline cards say "Not checked".
- **Segmented control** for language (Hinglish / English). **Select** for card count. **Textarea** for notes.
- **Status pill** in the header: Gemma connected, or Offline mode. Never colour alone: text always says it.
- **Theme switch:** an icon button (moon) with `aria-pressed`, 44px, in the header next to the status pill.
- **Verifier panel:** a plain sentence plus a disclosure listing removed cards with the reason.

## Copy rules
- Verb + object on buttons ("Make cards", "Show answer"). One label per intent everywhere.
- Never "Please", "Successfully", "Invalid", "You entered". Say what happened, why if useful, and what to do.
- Destructive actions restate the consequence: "Delete all 12 cards? This can't be undone."
- No em dashes in visible copy. No invented numbers. Real names and real text in examples.
- Voice: warm, brief, plain English with a little Hinglish where it fits (the grade labels, the odd greeting).

## States and edge cases (all designed)
Empty first use; empty after clearing; all caught up; one card; many cards (strip stacks cap at 8 and show "+n");
very long question or answer (wraps, never overflows); loading (about 30 to 45 seconds with Gemma, so the page says so and
shows elapsed time); Gemma offline (works with simple rules, labelled); rate limited (says how long to wait); server error;
blocked storage (works for the session, says it will not be saved); reduced motion; dark mode; 320px width.

## Accessibility
Landmarks and a skip link; one `h1`; labelled controls (never placeholder-only); `aria-live` for status and results; visible
focus rings in the accent with offset; targets of 44px; text spacing overrides must not break layout; no `user-scalable=no`;
the strip has a text equivalent; keyboard works for everything (Space or Enter shows the answer, 1 to 4 grades).

## Do not
Identical card grids; nested cards; gradient text; neon or glow; decorative glass; emoji as icons; coloured left borders;
scroll cues; fake numbers; custom cursors; more than one accent; text under 16px for body; motion that is the only signal.

## Quality gate before shipping a change
1. The 8 control states exist. 2. The edge cases above still work. 3. Contrast measured on the render (4.5 text, 3 controls).
4. Squint test: primary, secondary and groups are still nameable. 5. Reduced motion and dark mode checked.
6. The browser tests pass and real screenshots were looked at. 7. Score the page with the 0 to 100 rubric (accessibility,
usability, visual quality, token compliance) and fix anything under 90 before calling it done.
