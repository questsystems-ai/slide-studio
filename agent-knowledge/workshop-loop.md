# The Workshop Loop: Building a Living Presentation with Claude

**Draft for paperHTML**
*Aaron + Claude Sonnet 4.6 — April 2026*

---

## Abstract

We built a broadcast-quality animated pitch deck in three sessions without touching any slide software. The result is a single self-contained HTML file that plays like a film: narrated audio, synchronized word highlighting, animated SVGs, staggered entrance effects, a collapsible slide gallery, and video sequences that wait for their last frame before advancing. This paper documents the method — the architecture decisions, the specific coding patterns, the prompt-and-build loop — and makes a broader observation: code improves not just when you touch it directly, but as a side effect of working on adjacent things.

---

## 1. The Problem with Slides

PowerPoint is optimized for the wrong thing. It's optimized for editing slides. What a solo presenter actually needs is to iterate on *ideas* — and then have the visual and audio output generated as a consequence.

The friction in slide software is enormous: you wrestle with alignment, fight with font sizes, rebuild layouts from scratch when content changes. None of that is thinking. It's formatting.

The alternative we built: the author narrates intent in plain language, and Claude writes the HTML, CSS, and JavaScript. The author reviews in the browser. If something's wrong, they describe it. Claude fixes it. No drag-and-drop. No format painter. No slide master.

---

## 2. The Architecture Decision: One File

The most important decision was: **no build step, no framework, no server dependency**.

The entire presentation is a single `.html` file. Every slide is a `<div class="layer">` with its own `<style>` block scoped inside it. Audio is loaded from a sibling `audio/` directory. SVGs are inline. Images are base64 data URIs.

This means:
- Zero configuration to open it
- The file *is* the product — no compilation, no bundling
- Claude can write and edit it directly with the Read/Edit tools
- Sharing is a single file copy

The JS engine is ~300 lines: a `SCENES` array drives everything. Each scene has `narrationHtml`, `minDuration`, and an optional `authorLocked` flag. The `showScene()` function adds `.active` to the right layer, which triggers all CSS transitions for that slide. Audio plays via `playSceneAudio()`, which resolves only when both the audio *and* `minDuration` are satisfied — or when the last video in a sequence fires its `ended` event.

---

## 3. Case Study: The Progress Bar Slide

Slide 5 (scene index 5 in the `SCENES` array, displayed as slide 6) shows eleven projects across three categories — Tools, Businesses, Applied AI Research — each with a horizontal progress bar and a completion percentage.

### 3.1 The Layout

Three-column CSS grid, one column per category. Each column has a header and a stack of project cards:

```css
#projects-scene {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 0 32px;
  padding: 28px 48px 28px;
}
```

Each project card (`.pcard2`) holds an icon, a name, a progress row, and a status label. The progress row is two elements: a track and a fill:

```html
<div class="prg-track">
  <div class="prg-fill" style="--pct:75%; transition-delay:0.25s"></div>
</div>
<div class="prg-pct">75%</div>
```

### 3.2 The Animation: CSS Custom Properties + Transition

The fill bar starts at width 0. When the slide becomes active, the JS engine adds `.active` to the parent `.layer`. A CSS rule reacts:

```css
.prg-fill {
  width: 0;
  transition: width 0.7s ease;
}
.layer.active .prg-fill {
  width: var(--pct);
}
```

The target width is stored as the `--pct` custom property inline on each element. This means the HTML carries its own data — no JS lookup required at animation time. The transition just reads the property and fills to that width.

### 3.3 The Stagger

Each bar gets a `transition-delay` set directly in the `style` attribute. The delays increase as you move down the list, creating a waterfall effect:

```html
<!-- Tools column, staggered 0.1s apart -->
<div class="prg-fill" style="--pct:100%; transition-delay:0.1s"></div>
<div class="prg-fill" style="--pct:75%;  transition-delay:0.25s"></div>
<div class="prg-fill" style="--pct:75%;  transition-delay:0.4s"></div>
...
<!-- Businesses column, starts at 1.8s (after tools finish) -->
<div class="prg-fill" style="--pct:30%;  transition-delay:1.8s"></div>
...
<!-- Research column, starts at 3.0s -->
<div class="prg-fill" style="--pct:15%;  transition-delay:3.0s"></div>
```

The columns animate in sequence — tools fill first, then businesses, then research. Each column's delay starts just after the previous column finishes, giving the eye somewhere to go.

### 3.4 Color Theming by Category

Each column has a category class. The fill color is set per category:

```css
.cat-tools2 .prg-fill { background: linear-gradient(90deg, #0c8de9, #38bdf8); }
.cat-biz2   .prg-fill { background: linear-gradient(90deg, #c8a96e, #f0d090); }
.cat-res2   .prg-fill { background: linear-gradient(90deg, #818cf8, #b06be0); }
```

Blue for software tools. Gold for businesses. Purple for research. The gradient gives each bar a slight 3D feel without any extra markup.

### 3.5 The Narration Calculation

The original narration said "the average across all seven is about forty-one percent." Both numbers were wrong. In session 3, while fixing an unrelated audio mismatch, we re-read the actual `--pct` values from the HTML:

```
100 + 75 + 75 + 100 + 65 + 100 + 30 + 80 + 15 + 15 + 15 = 670
670 ÷ 11 = 61%
```

The narration was updated to match, audio was regenerated, and the slide became accurate. This is the correction loop in practice: the code is the source of truth, not the narration that was written before the code existed.

---

## 4. The Improvement Phenomenon

Here is the observation worth publishing:

> *Code improves not just when you touch it directly, but as a side effect of working on adjacent things.*

In three sessions, we built fourteen slides. Each slide has its own style block, its own SVG or layout, its own animation logic. But the slide engine — the JavaScript that runs all of them — improved continuously as a side effect.

When fixing a pause button (session 1), we discovered that CSS animations weren't respecting the paused state. The fix: a body class (`.anim-paused`) that sets `animation-play-state: paused` globally. That one fix improved every animated slide simultaneously — even slides we hadn't touched yet.

When fixing the narration progress underline (session 1), we discovered the tick loop was updating `--speak-progress` even when paused. The fix was one condition: `if (playing)`. That one line made the underline accurate for every slide.

When fixing the slide counter (session 2), we discovered it used raw array index while the gallery used display-number logic. Unifying them via `_displayNum()` made the counter correct everywhere.

None of these fixes were the primary task. They were discovered — and fixed — as a consequence of being in the code.

This is different from how software is typically built. Traditional engineering separates concerns: one person owns the animation engine, another owns the audio layer, another owns the UI. The cost of that separation is that improvements don't propagate — each team member only improves what they own.

When a single agent has full context and full write access to a single file, improvements propagate everywhere. The file gets better holistically, not just in the place you're looking.

---

## 5. The Loop, Described

The method is simple enough to state as a loop:

1. **Author describes the slide in plain language.** Not "make a bar chart" — more like "show each project as a progress bar, grouped by category, filling in from left to right as the slide opens."
2. **Claude writes the HTML, CSS, and JS.** It reads the existing file first to understand the patterns already in use, then writes code that fits.
3. **Author reviews in the browser.** Something's off — a label is truncated, a color clashes, the stagger feels mechanical.
4. **Author describes the correction.** Claude edits the relevant block.
5. **Repeat until it feels right.**

The key is that the author never leaves their role. They are always describing, never formatting. The distance between "I want this" and "this exists" is one message.

---

## 6. What This Implies

The presentation format itself is changing. PowerPoint was designed for a world where slides were projected to a room. The author made slides, then stood in front of them and spoke.

What we built is something different: the narration and the visuals are synchronized at the word level. The audio drives the timing. The slide waits for the last video frame before advancing. The author's voice is part of the artifact — not a separate performance added on top.

This is closer to film than to slides. And it was built not by a team with a video budget, but by one person and a language model, in a text editor, in three sessions.

The format is available to anyone. The method is replicable. The file is one HTML document.

That's the point.

---

## Appendix: Key Code Patterns

**Scene activation trigger**
```js
function showScene(index) {
  document.querySelectorAll('.layer').forEach((l, i) => {
    l.classList.toggle('active', i === index);
  });
}
```

**Audio + minDuration gate**
```js
audio.onended = () => {
  const minDur = SCENES[index]?.minDuration || 5;
  const elapsed = getSceneElapsed();
  if (elapsed < minDur) {
    setTimeout(resolve, (minDur - elapsed) * 1000);
  } else {
    resolve();
  }
};
```

**Video sequence with post-roll advance**
```js
v3.addEventListener('ended', () => {
  [v1, v2, v3].forEach(v => { v.currentTime = 0; v.style.opacity = '1'; });
  setTimeout(() => {
    if (audioFinishedResolve) { audioFinishedResolve(); audioFinishedResolve = null; }
  }, 2000);
}, { once: true });
```

**Pause-freezing CSS animations**
```css
.anim-paused .layer.active * {
  animation-play-state: paused !important;
}
```

**Word-level narration underline**
```css
#narration-text::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0;
  width: var(--speak-progress, 0%);
  height: 2px;
  background: #4da6ff;
  transition: width 0.1s linear;
}
```
```js
// Only updates when playing — freezes on pause
if (playing) {
  document.getElementById('narration-text')
    .style.setProperty('--speak-progress', `${t * 100}%`);
}
```

---

*Written in the same session that built the slides it describes.*
