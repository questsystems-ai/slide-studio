# Lessons Learned: Building the Dad Pitch

These are hard-won lessons from building a 14-slide animated presentation (the "dad pitch") across multiple sessions. Apply these to every new project.

---

## Architecture

**One file is the product.**
The entire presentation is a single `.html` file. No build step, no framework, no server dependency. This means Claude can read and edit it directly. The file IS the artifact.

**The SCENES array drives everything.**
Each scene: `{ narrationHtml, minDuration, authorLocked? }`. The JS engine reads it. The slides are just `<div class="layer">` elements — the SCENES array provides narration and timing. Keep these in sync.

**CSS scope everything to `.layer.active`.**
Slide animations must be triggered by the parent layer gaining the `.active` class. Never use `@keyframes` that start on page load. Pattern:
```css
.layer.active .my-element { opacity: 1; transform: translateX(0); }
```

---

## Animation Patterns That Work

**Stagger via inline `transition-delay`.**
Don't use JS timers for stagger effects. Put `transition-delay` inline on each element. The HTML carries its own timing data.

**CSS custom properties for animated values.**
Store the target value as a CSS variable (`--pct: 75%`) and have the CSS read it. No JS lookup needed at animation time.

**`anim-paused` body class for global pause.**
When the user pauses, add `.anim-paused` to `<body>`. Then:
```css
.anim-paused .layer.active * { animation-play-state: paused !important; }
```
This freezes all animations on the active slide simultaneously.

**Video chains: resolve on last video's `ended` event.**
For slides with video sequences, the scene should not advance until the last video fires `ended`. Use `audioFinishedResolve` as the gate — the video's ended handler calls it after a 2s post-roll.

**`minDuration` is a sentinel, not a timer.**
Set `minDuration` to the expected slide duration as a fallback if audio/video fails. Normal advance happens via the audio `ended` event + the duration gate.

---

## Narration

**`authorLocked: true` protects human-edited narration.**
If the author edits narration directly in the browser (via the Edit button), set `authorLocked: true`. Never overwrite these without explicit permission.

**Code is the source of truth, not the narration.**
The narration should describe what the visuals actually show. If a progress bar SVG has 11 projects averaging 61%, the narration must say 61% — not a value written before the code existed. Always verify numbers against the actual code.

**Keep narration under 60 words per slide.** Conversational, direct. Read it aloud — if it sounds like a term paper, rewrite it.

---

## Common Bugs and Fixes

**Scene counter vs display number.**
Array index ≠ display number when scenes are skipped. Always use a `_displayNum(index)` helper. Unify all counter displays through it.

**Narration underline freezes on pause.**
The `--speak-progress` CSS variable must only update when `playing === true`. One condition: `if (playing) { ... setProperty ... }`.

**Replay hang on complex scenes.**
If a scene has animation state that accumulates, reset it in `showScene()`. Pattern: `_myAnimVar = false; // reset on every scene show`.

**CSS transition: none on scenes with no fade.**
For scenes that should cut (not cross-fade), add `#scene-N { transition: none !important; }` — otherwise the fade creates a ghost frame on replay.

---

## The Workshop Loop

1. Author describes the slide in plain language — layout, feel, what should happen.
2. Agent reads the existing file, writes code that fits the existing patterns.
3. Author reviews in the browser. Describes what's wrong.
4. Agent fixes the specific block. Doesn't rewrite unrelated code.
5. Repeat until it feels right.

The key is that improvements propagate holistically. When you fix one animation pattern, it improves every slide that uses it — even ones not yet touched. This is the compounding effect of one-file architecture.

---

## Visual Quality Bar

Before marking a slide done, check:
- Does the animation start cleanly from a neutral state when the slide activates?
- Does it reset cleanly when you replay?
- Are all text elements readable against the background?
- Do animated elements stay within the visible area at all animation stages?
- Is there any visual overlap between text labels, shapes, or SVG paths?
- Does the narration timing feel matched to the visual sequence?
