# PCR Agent Build — What We're Trying to Do

## Goal
Build the PCR (Polymerase Chain Reaction) explainer presentation using the Agent Assist
web interface — the way a customer would. No dev console, no Claude Code, no YAML files.
Just: open the browser, talk to the agent, get a presentation.

## Why
This is the product readiness test. If the agent can take "build me a PCR explainer"
and produce a working animated presentation, the SaaS model is viable. If it can't,
we know exactly what to fix before launch.

## What's Been Built (as of 2026-04-07)
- `serve.py` — upgraded with `/api/claude` proxy endpoint. API key loads from `.env.local`,
  never exposed to the browser. Also handles `/save` for writing files back to disk.
- `index.html` — Agent Assist panel now calls real Claude (claude-sonnet-4-6) via the proxy.
  Conversation history is tracked. Claude returns slide specs as JSON; the UI parses them,
  shows a preview, and offers a "Save as new presentation" button that writes a self-contained
  HTML file via `/save`.

## What the Agent Does
System prompt teaches Claude:
- The SCENES array format (narrationHtml, minDuration)
- How to return structured slide specs as a JSON block
- How to describe visual layouts per slide

When the user says "build me a PCR explainer", Claude returns 6-8 slide specs.
The UI renders a preview and saves `pcr-explainer.html` to disk.

## What's NOT Done Yet
- The saved HTML has placeholder layout notes instead of real SVG/CSS visuals.
  After the agent writes the content scaffold, the next step is building the visuals
  slide-by-slide (back to the workshop loop).
- No ElevenLabs TTS in the agent flow yet — audio needs to be generated separately.
- No streaming — Claude response arrives all at once.

## The Business Model Question
slide-studio ships as hosted SaaS (server-side API keys, subscription).
Do NOT open-source the architecture or publish the workshop-loop paper.
The PCR build is a private readiness test, not a launch demo.

## How to Run
```bash
python serve.py
# open http://localhost:8500/index.html
# click Agent Assist (top right)
# type: "Build me a PCR explainer — 6 slides, general science audience"
```
