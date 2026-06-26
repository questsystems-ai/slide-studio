# slide-studio

## Startup Protocol
On every new conversation, run `/initiate` before anything else. Zero ramp-up time between sessions.

## Product Vision

**Product name:** presentation.html
**Tagline:** A guy and his Claude making a presentation.

presentation.html is a live, collaborative animated slide builder — the anti-PowerPoint. Instead of wrestling with slide software, the author narrates intent and Claude builds it: animated SVG figures, narrated audio via ElevenLabs TTS, image injection (generated or user-provided). The result is a single self-contained HTML file that plays like a film.

**Two modes, one product:**
- **Live build mode** (current): author + Claude iterate in VS Code. Author describes what they want, Claude writes it. Edit button lets the author fix narration text directly in the browser; changes save back to disk and are marked `authorLocked: true` so Claude never overwrites them.
- **Embedded agent mode** (roadmap): ships with a pre-trained agent in the UI. No VS Code required. Anyone can open presentation.html in a browser and build a presentation by talking to it.

**First example:** Dad pitch — Aaron's citizen scientist / gentleman scientist framing. Source: `notes/dad-pitch-2026.yaml`.

**What makes it different from presentaHTML:**
- presentaHTML = YAML → auto-narrated explainer. Best for: technical step-by-step processes (SHA-256, PCR). Fully automated.
- presentation.html = collaborative, author-driven. Best for: narrative presentations, pitches, talks. Author is in the loop at every step.

**End state:** Takes over from PowerPoint for anyone who wants something more alive than slides and more personal than a generated video.

**Target audience:** Initially — Aaron's own pitches and talks. Then: researchers, founders, educators who want broadcast-quality presentations without video production overhead.

**Go-to-market:** Ship as an open product alongside the citizen scientist paper series. The dad pitch is the first public demo.

## Stack
- Single-file HTML/CSS/JS (no build step)
- ElevenLabs TTS + word-level timing API for narration audio
- Python `serve.py` dev server (POST /save for in-browser edits)
- Animated SVGs built inline per slide
- Images: embedded as base64 data URIs

## Author-Locked Narration

Scenes in `presentation.html`'s `SCENES` array with `authorLocked: true` were edited directly in the browser by Aaron. **Never overwrite `narrationHtml` for these scenes without explicit permission.** Ask first. Unlocked scenes are fair game.

To check locked scenes:
```bash
grep -o 'authorLocked":true' presentation.html | wc -l
```

## Dev Server

```bash
python serve.py
# serves at http://localhost:8500/presentation.html
```

POST /save with X-Filename header writes files back to disk (powers the in-browser Edit button).

## Complexity Check (Self-Audit Rule)
After 2 failed attempts at the same problem: STOP. Diagnose what's tangled, propose a focused fix, estimate the effort, let the user decide. Don't brute-force.

## When Searching
If Glob or Grep returns a directory or file path that's plausibly relevant to the question, read inside it before answering. Don't stop at the listing.

## Git Workflow
- Default branch: `main`. Use `dev/wip` for in-progress work, never push broken code to `main`.
- Never commit `.env.local`, `node_modules/`, `__pycache__/`, `*.pyc`
- Commit often — clean git state = fast next session recovery

## Session Continuity
- Handoff report: `scripts/output/session-handoff-YYYYMMDD-HHMM.md` (timestamped, written by `/terminate`, read by `/initiate`)
- Session log: `scripts/output/session-log.md` (auto-logged via hooks, crash insurance)
- End of session: run `/terminate` — commit check, handoff write, memory update
- New terminal: open a new terminal in this project directory and run `claude`

## Budget Discipline
- Run as Sonnet (cost-aware mode always active)
- Opus only as a contained subagent for frontier reasoning — announced before launch
- ~25 message soft cap per session — open a fresh terminal and run `claude` to swap context
