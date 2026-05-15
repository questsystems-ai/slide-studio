---
name: terminate
description: End-of-session — generate handoff report, suggest commit, and wrap up
user-invocable: true
---

## Session Termination Procedure

The user is ending this session. Generate a handoff report so the next session can pick up instantly.

### Step -1: Write termination sentinel (do this BEFORE ANYTHING ELSE)

Write a sentinel file to signal that termination is in progress:

```
scripts/output/.terminating
```

Contents: one line — `TERMINATING: <timestamp> — <one-line description of what was in flight when terminate was called>`

Example: `TERMINATING: 2026-04-23 18:30 — green angle added to §12.5, hash re-sealed, ready to commit`

This file is the crash-recovery signal. If compaction or a context limit interrupts the terminate sequence before it completes, the next session's `/initiate` will find this file and know to complete the terminate rather than resume work. Delete this file as the very last action in Step 5.

### Step 0: Commit check (do this FIRST)

Run `git status` and `git diff --stat`. Check for two things:

**1. Untracked files that were actively worked on this session:**

⚠️ **CRITICAL — flag these immediately.** Untracked files have NO git history. If the session ends without committing them, every edit made this session is unrecoverable. For any untracked file that was created or edited this session, say:

> "⚠️ `<filename>` is untracked — it has no git history. All edits this session are unrecoverable without a commit. Commit it now before we write the handoff."

Suggest: `git add <file> && git commit -m "init: <filename> — <one-line description>"`

**2. Uncommitted changes to tracked files:**

⚠️ **Stop and tell the user before proceeding.** Uncommitted work forces the next session to spend tokens reconstructing state from diffs instead of reading clean commit history. That exploration costs real money.

Suggest a commit message covering the session's work and ask the user to commit before you continue with the handoff. Only proceed to Step 1 after the user responds (commit, skip, or defer).

### Step 0.7: Deploy branch check

Detect whether this project deploys to the web, and whether the current branch's work is live.

```bash
current_branch=$(git branch --show-current)
default_branch=$(git remote show origin 2>/dev/null | grep "HEAD branch" | awk '{print $NF}')
echo "current: $current_branch | default: $default_branch"
[ -f vercel.json ] && echo "vercel.json: present" || echo "vercel.json: none"
[ -f netlify.toml ] && echo "netlify.toml: present" || echo "netlify.toml: none"
ls .github/workflows/*.yml 2>/dev/null | xargs grep -l "branches:" 2>/dev/null | head -3
```

**Interpret and act:**

- **`vercel.json` present** → Vercel deploy. Default deploy branch is `master` or `main` (check vercel.json for `git` config; if absent, use the repo default branch from above).
- **`.github/workflows/` with `branches: [X]`** → GitHub Actions deploys from branch X.
- **`netlify.toml`** → check `[context.production]` for branch setting.
- **None of the above** → not web-deployed; skip to Step 1.

**If web-deployed and current branch ≠ deploy branch:**

Check whether uncommitted work or unpushed commits exist on the current branch:
```bash
git log origin/[deploy-branch]..HEAD --oneline 2>/dev/null | head -10
```

If there are commits not yet on the deploy branch, ask:

> "Your changes are on `[current-branch]`. [Platform] deploys from `[deploy-branch]` — so these changes aren't live yet. Merge to `[deploy-branch]` and push to go live now, or stay on `[current-branch]`?"

If they say go live:
```bash
git checkout [deploy-branch] && git merge [current-branch] --ff-only && git push origin [deploy-branch] && git checkout [current-branch]
```

**If web-deployed and current branch == deploy branch:** confirm a push happened this session, or offer to push now.

**Always record in handoff** under Current State: `[site/project] → [deploy-branch] → [platform] (auto-deploy on push)`

### Step 1: Gather state

Run these in parallel:
- `git log --oneline -5` — recent commits
- `git status` — confirm current state after any commit

### Step 2: Write the handoff report

Write a **timestamped** handoff file: `scripts/output/session-handoff-YYYYMMDD-HHMM.md` (e.g. `session-handoff-20260331-1430.md`). Use today's date and current time. Create the directory if needed. Keep it under 80 lines. Include:

**Settled decisions** (names chosen, acronyms selected, options picked): log these explicitly in Key decisions as `[Thing]: chosen value` — e.g. `[Acronym]: PULSE = Portable Unified Lightweight Scalable Engine`. These are the facts most likely to be asked about in future sessions and least likely to survive as only a memory.

1. **The Product** — one paragraph: what this app/service does, who it's for
2. **Stack** — one line: framework, language, DB, key APIs/services
3. **Business Context** — one line: who's building it, what stage, what's the goal
4. **Current State** — today's date, current branch, what just got done this session, what's pending/blocked
   - **Deployments** — for any web-deployed project touched this session, explicitly record: project name, deploy branch, deploy trigger (e.g. "akushnerphd.me → master branch → Vercel auto-deploy on push"). Future sessions must not have to rediscover this.
5. **Stopped Mid-Task** — if the session ended before completing something in progress, say so explicitly: what task, what was left, where to pick it up. This is distinct from Pending (backlog) — it's the thing the user would have done next if cost hadn't forced a stop. If nothing was mid-flight, omit this field entirely.
6. **Key files** — only files the next session will definitely need to touch
7. **Quick verify** — a shell snippet to confirm the app runs and recent work is intact

Do NOT include: full architecture docs, file trees, API specs, or anything already in CLAUDE.md or memory files. The goal is minimal context that gets a fresh session productive in 30 seconds.

### Step 2.5: Write session index entry (L2 recall layer)

Append a brief entry to `scripts/output/session-index.md` (create if it doesn't exist). This is the fast-search layer for `/recall` — write it to be keyword-rich and scannable, not narrative.

Format:
```
## YYYY-MM-DD ~HH:MM · <project/repo name>
Keywords: <comma-separated topics, decisions, names, acronyms discussed>
- [one line per significant exchange: topic + outcome/decision]
- [...]
```

Example:
```
## 2026-05-05 ~14:00 · parent
Keywords: bi-temporal, recall, TRACER, session-index, memory types, JSONL search
- bi-temporal convention added to MEMORY.md and CLAUDE.md — append <!-- updated --> on all edits
- TRACER confirmed not implemented; memory-engine/ has draft paper only
- recall.py built: L1 (session-index) + L2 (raw JSONL) two-layer search across all projects
- recall skill added to .claude/skills/recall/SKILL.md
```

Keep each entry under 15 lines. The file is append-only — never edit past entries.

### Step 3: Update memory if needed

If anything happened this session that future sessions should know about (feedback, corrections, project decisions), save it to the appropriate memory file. Don't duplicate what's already in memory.

### Step 4: Confirm clean state

If the user committed in Step 0, verify with `git status` that the working tree is clean. If they skipped, note the uncommitted files in the handoff report under a `## ⚠️ Uncommitted work` section so the next session knows to deal with it immediately.

### Step 5: Sign off

Delete the sentinel file and your session state file:

```bash
rm scripts/output/.terminating
# Delete your own session state file (the one you wrote during /initiate)
rm scripts/active-sessions/session-<your-timestamp>.md 2>/dev/null
```

Output a brief summary:
```
## Session Complete

**Committed:** [yes/no — commit hash if yes]
**Handoff:** scripts/output/session-handoff-YYYYMMDD-HHMM.md
**Key takeaway:** [one sentence — what was accomplished or decided]

Ready to close. Next session: run `/initiate` to pick up where we left off.
```
