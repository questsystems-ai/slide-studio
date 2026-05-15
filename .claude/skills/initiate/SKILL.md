---
name: initiate
description: Session startup — read handoff, check git state, orient on what's next
user-invocable: true
---

## Session Initiation Procedure

You are starting a new session. Run through these steps IN ORDER to get fully oriented, then present a concise briefing to the user.

### Step 0: Check reminders

Before anything else, check `notes/reminders.md`:

```bash
cat notes/reminders.md 2>/dev/null
```

If the file exists and has entries, they become the **first thing in the briefing** — before handoffs, before git state. MUST items get called out directly: "You said this needs to happen today: [reminder]. Do you want to start here?"

If no reminders file or file is empty, proceed silently.

### Step 0.1: Check for interrupted terminate or mid-batch execution

Check for the termination sentinel AND the last-exchange record:

```bash
cat scripts/output/.terminating 2>/dev/null
cat scripts/output/.last-exchange.md 2>/dev/null
```

**If `.terminating` exists:** a previous session was interrupted mid-terminate. **Do not read the handoff or present a briefing.** Instead:

1. Tell the user: "Previous session was interrupted mid-terminate. Completing it now."
2. Show the sentinel contents (what was in flight)
3. Run the full `/terminate` procedure from Step 0 — it will write the handoff, update memory, and clean up. The sentinel file will be deleted when terminate completes successfully.

**If `.last-exchange.md` exists with `Status: executing`:** a previous session was interrupted mid-batch. Surface this **at the top of the briefing** under "Stopped Mid-Batch":

- Show the verbatim User Request
- Show the verbatim Claude Commitment (task list)
- Say: "Previous session committed to these tasks and was interrupted before finishing. Complete remaining tasks now, or skip?"

The compaction summary may have captured some tasks as done — cross-reference it to determine which items are still pending.

**If `.last-exchange.md` exists with `Status: completed` or `Status: pending`**, proceed normally — but note: `Status: completed` only means the *committed batch* finished. A subsequent session may have crashed without writing a new commitment. Step 6c (JSONL check) is the backstop for this case.

If neither file exists, proceed normally to Step 0.5.

### Step 0.5: Session state — write yours, read others

**Write your own session state file** so other instances know you're active:

```bash
# Timestamp for this session (use current time)
echo "instance: session-$(date +%Y%m%d-%H%M)
started: $(date '+%Y-%m-%d %H:%M')
repo: $(basename $(pwd))
working-on: initiating
files-active: (none yet)
last-action: $(date '+%Y-%m-%d %H:%M')" > scripts/active-sessions/session-$(date +%Y%m%d-%H%M).md
```

**Read all other session state files** (not your own — read ones written before ~30 seconds ago):

```bash
ls scripts/active-sessions/session-*.md 2>/dev/null
```

If other session files exist, read each one. Surface them in the briefing under "Other Active Sessions". Check for file conflicts: if another session lists a `files-active` entry that you are also about to work on, flag it explicitly.

**IMPORTANT — session state files are unreliable.** A prior session may show `working-on: initiating` even if it did 200+ turns of work — the session never updated the file as it progressed. Do NOT use the session state file to conclude "nothing was done." It is only useful for knowing which sub-repo was active. The JSONL is the only ground truth for what actually happened.

**JSONL drill-down (optional, on demand):** If you need deeper context on what another instance was doing, extract their recent human turns:

```bash
# List recent JSONL files for this project (second-most-recent = likely the other instance)
ls -t /c/Users/aaron/.claude/projects/C--Users-aaron-Documents-a-i-rons-projects/*.jsonl 2>/dev/null | head -5

# Extract last 10 human turns from a specific JSONL file:
python3 -c "
import sys, json
lines = open(sys.argv[1]).readlines()[-300:]
turns = []
for line in lines:
    try:
        o = json.loads(line)
        msg = o.get('message', {})
        if msg.get('role') == 'user':
            content = msg.get('content', '')
            if isinstance(content, list):
                content = ' '.join(p.get('text','') for p in content if isinstance(p,dict))
            if content.strip():
                turns.append(content.strip()[:300])
    except: pass
print('\n---\n'.join(turns[-10:]))
" <jsonl_path>
```

Only run the JSONL drill-down if: (a) another session file is present AND (b) you need context beyond what the session state file provides. Do not run it by default — it loads significant context.

### Parent repo lookup rule (sub-repos only)

If this session is running inside a sub-repo (i.e. `../CLAUDE.md` exists and belongs to `a-i-rons_projects`), apply this rule throughout the session:

**Before saying "I haven't heard of X" or "I can't find X"** — check the parent repo first:

```bash
# Check parent CLAUDE.md for the concept
grep -i "<term>" ../CLAUDE.md 2>/dev/null | head -10

# Check parent notes for broader context
ls ../notes/ 2>/dev/null
grep -rl "<term>" ../notes/ 2>/dev/null | head -5
```

Portfolio-level concepts (formats, frameworks, terminology, cross-repo decisions) are defined in the parent repo and won't appear in the sub-repo's files. If found in the parent, read the relevant section and report back: "Found in parent repo — [summary]." If not found in the parent either, then it's genuinely unknown.

### Prior Work Recall (active throughout the session)

This rule applies **any time the user references something with a definite article or possessive** — "the voiceover tool", "our simulation design", "the paper we wrote", "that approach we discussed".

**Do not treat these as fresh requests.** They are references to prior collaborative work. Before responding or building:

1. Search the JSONL transcripts for the keyword(s):
   ```bash
   grep -ao '"text":"[^"]*<keyword>[^"]*"' <most_recent_jsonl> | sed 's/"text":"//;s/"$//' | head -20
   ```
2. Search `notes/` and `memory/` for the keyword:
   ```bash
   grep -rl "<keyword>" notes/ memory/ 2>/dev/null | head -5
   ```
3. Report what was found and confirm it matches what the user meant — then proceed.

**Signal words that trigger this:** "the [thing]", "our [thing]", "that [thing] we...", "the one where...", "like we did with..."

If nothing is found in transcripts or notes, say so explicitly before asking the user to re-explain. The log is ground truth — absence should be stated, not assumed.

### Step 1: Read the handoff report

Glob `scripts/output/session-handoff-*.md` for timestamped handoffs, and also check for legacy `scripts/output/session-handoff.md`.

**If only one file exists:** read it — it is the most direct summary from the previous session.

**If multiple exist:** read ALL handoffs from the current day (same `YYYYMMDD` prefix as today) automatically — do not ask first. Older handoffs (prior days) can be skipped unless the most recent day has none. Each handoff you read will become its own section in the Step 7 briefing (see "Previous Sessions" format below). After presenting all sessions, ask the user which one to continue.

### Step 2: Check uncommitted changes

Run `git status` and `git diff --stat`.

Identify:
- Modified files (what areas of the codebase were touched)
- Untracked files (new features/files added)
- Staged vs unstaged changes

If there are changes beyond what the handoff report describes, note them — they may represent work done after the report was written.

### Step 3: Recent commits

Run `git log --oneline -10`.

Summarize what the last few commits accomplished. Note the gap between committed work and uncommitted work.

### Step 4: Check memory

Read the memory index (`MEMORY.md` in the project's memory directory) and scan for any memories that seem relevant to what's pending. Read the most important ones (especially feedback and project memories). Don't read all files — just the ones that matter for what's next.

**Past decision lookup:** If the user asks about a specific past decision (a chosen name, acronym, option picked, etc.) and the handoffs + memory don't contain it — grep the JSONL transcripts before asking the user to repeat themselves. The transcripts are the ground truth. Search with:
```bash
grep -ao '"text":"[^"]*<keyword>[^"]*"' <jsonl_path> | sed 's/"text":"//;s/"$//' | head -20
```
Use the most recent JSONL first (`ls -t /c/Users/aaron/.claude/projects/<project-id>/*.jsonl | head -3`). Do not surface "I can't find it" until you've checked the transcripts.

### Step 5: Verify cost-aware mode

Check that you are running as **Sonnet** (not Opus). If you detect you are Opus, warn the user immediately:

```
⚠️ COST WARNING: This session is running on Opus. For cost efficiency, restart with Sonnet selected.
Opus should only be used as a subagent for frontier reasoning tasks (see /cost-aware skill).
```

If running as Sonnet, confirm briefly: `✅ Running as Sonnet (cost-aware mode active)`

Read the cost-aware skill (`.claude/skills/cost-aware/SKILL.md`) to load the escalation protocol. All subagents launched this session must use `model: "sonnet"` or `model: "haiku"` unless an explicit Opus escalation is triggered.

### Step 6: Reconstruct the active problem

**Always run this step**, even if the handoff looks clean. This is the crash-recovery backstop.

#### 6a: Git diff (tracked changes)

1. Run `git diff HEAD --stat` to identify the most-changed tracked files
2. For the top 2-3 most modified files, run `git diff HEAD -- <file> | head -120` to read the actual changes
3. If a `copilot-logs/` directory exists, check it: `ls -t copilot-logs/ | head -3`, then `tail -80` on the newest one

#### 6b: Untracked file scan (catches crashes on new files)

New files are invisible to `git diff`. Run this to find untracked files modified more recently than the most recent handoff:

```bash
# List all untracked files with timestamps, newest first
git ls-files --others --exclude-standard | xargs -d '\n' ls -lt --time-style="+%Y-%m-%d %H:%M" 2>/dev/null | sort -k6,7 -r | head -20
```

**Flag any untracked file modified after the last handoff timestamp.** These are the strongest signal of work done in a crashed session — the session created or modified the file but never wrote a handoff. Cross-reference against the handoff contents: if a file appears here that the handoff doesn't mention, it was likely created or edited after the handoff was written (i.e., in a subsequent crashed session).

#### 6c: JSONL last-session check (always run)

**Always run this.** The JSONL is ground truth — it captures what actually happened even when `.last-exchange.md` shows `Status: completed` and no handoff exists.

```bash
# Get the two most recent JSONL files (most recent = this session, second = prior session)
ls -t /c/Users/aaron/.claude/projects/C--Users-aaron-Documents-a-i-rons-projects/*.jsonl 2>/dev/null | head -3
```

Read the second-most-recent JSONL (the prior session). Run this exact script — use `py -3` on Windows, `python3` on Mac/Linux. The `errors='replace'` and ASCII output avoid encoding crashes on Windows:

```bash
py -3 -c "
import json, os
path = 'C:/Users/aaron/.claude/projects/C--Users-aaron-Documents-a-i-rons-projects/<second-most-recent>.jsonl'
size_mb = os.path.getsize(path) / 1024 / 1024
with open(path, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Extract ALL turns first to get true count
all_turns = []
for line in lines:
    try:
        o = json.loads(line)
        msg = o.get('message', {})
        role = msg.get('role', '')
        content = msg.get('content', '')
        if isinstance(content, list):
            content = ' '.join(p.get('text','') for p in content if isinstance(p,dict) and p.get('type')=='text')
        content = content.strip()
        if content and role in ('user','assistant'):
            all_turns.append((role, content))
    except: pass

total_turns = len(all_turns)
print(f'=== SESSION SIZE: {total_turns} turns, {size_mb:.1f} MB ===')

# Scale sampling depth based on session size
# Small session (<50 turns): last 10 turns
# Medium session (50-100 turns): last 20 turns
# Large session (>100 turns): first 3 + middle 5 + last 20
if total_turns > 100:
    sample = all_turns[:3] + all_turns[total_turns//2 - 2:total_turns//2 + 3] + all_turns[-20:]
    label = f'LARGE SESSION ({total_turns} turns) — first 3 + middle 5 + last 20'
elif total_turns > 50:
    sample = all_turns[-20:]
    label = f'MEDIUM SESSION ({total_turns} turns) — last 20'
else:
    sample = all_turns[-10:]
    label = f'SMALL SESSION ({total_turns} turns) — last 10'

print(f'=== {label} ===')
for role, content in sample:
    print(f'[{role}] {content[:300].encode(\"ascii\",\"replace\").decode(\"ascii\")}')
    print()

# Terminate check — scan last 100 lines for any signal that /terminate ran
print('=== TERMINATE CHECK ===')
found = False
for line in lines[-100:]:
    try:
        o = json.loads(line)
        msg = o.get('message', {})
        content = msg.get('content', '')
        if isinstance(content, list):
            content = ' '.join(p.get('text','') for p in content if isinstance(p,dict) and p.get('type')=='text')
        cl = content.lower()
        if any(w in cl for w in ['terminate','session-handoff','handoff report','wrap up','session end']):
            print('FOUND:', content[:200].encode('ascii','replace').decode('ascii'))
            found = True
    except: pass
if not found:
    print('No terminate signal found.')
" 2>&1
```

Look for:
- The **session size** — turn count and MB. A large session (>100 turns) with no terminate means significant unrecorded work.
- The **last user message** — what was the user asking for when the session ended?
- The **last assistant message** — did it complete, or cut off mid-task?
- Any tool calls in progress when the session terminated
- Whether `/terminate` ran (terminate check output)

**Terminate check result:**
- If terminate signal found → session ended cleanly, handoff should exist
- If **no terminate signal** → session ended abruptly (crash, restart, closed terminal). Flag this: `⚠️ No terminate detected — session ended without handoff`
- If **no terminate signal AND > 50 turns** → escalate loudly: `🚨 Large session ({N} turns) ended without terminate — significant work has no handoff. Read the topic scan above carefully.`

**2-sentence summary:** After reading the turns, synthesize what happened in exactly 2 sentences and surface it in the briefing under **Last Session Summary**. Include turn count. Format: "We were working on X [what/where] across N turns. The session ended Y [cleanly with handoff / abruptly without terminate]."

If the session ended mid-task (tool calls with no following response, or a response that says "building..." / "writing..." with no Write/Edit tool call after it), surface this under **Stopped Mid-Task** in the briefing.

#### Synthesize

From 6a + 6b + 6c, report:
- **What was being built or fixed** (the feature or bug)
- **What state it was in** (complete, mid-implementation, or broken)
- **What the likely next action was** (the thing the user would have typed next)

If the handoff already covers this clearly, you can be brief here. If the session crashed with no clean handoff, this becomes the primary recovery signal.

### Step 7: Present the briefing

**Before writing the briefing**, run `date` to get the OS clock. Use this — not the injected `currentDate` — as the authoritative date. Derive the day of week and compute "tomorrow" so any date-specific reminders in the handoff can be verified (e.g. "Monday 5/5" gets caught as wrong if Monday is actually 5/4).

Output a concise briefing in this format:

```
## Session Briefing

### Today
[Day, Month Date Year — Time — from OS `date` command. e.g. "Sunday, May 4 2026 — 1:36 PM"]

### Reminders
[If notes/reminders.md has entries — show ALL of them here, MUST items first in bold. For MUST items: "You said this needs to happen today/Monday: [text]. Start here?" If empty, omit this section entirely.]

### Model
[Sonnet ✅ or Opus ⚠️ — with cost warning if Opus]

### Product
[One line — what this is, from handoff or CLAUDE.md]

### Previous Sessions
[One block per handoff read. If only one handoff, label it "Last Session". If multiple, label each by timestamp and one-line topic, then show done/pending for each. Example:]

**Session A — 2026-04-29 ~21:00 · Research/audiobook**
- Done: HN dive system, LLM sim bias field report, Patterns of Influence synopsis, Kokoro TTS
- Pending: voice choice when current book done; lateral thinking snapaper

**Session B — 2026-04-29 ~19:00 · Console Continuity editing**
- Done: dropped Identity Declaration layer, removed blog patterns, reordered sections
- Pending: human editing pass; §7 platform grid fix; [5] URL TBD; GitHub link TBD

### Other Active Sessions
[If other session files exist in scripts/active-sessions/ — list each: instance name, what they're working on, files active. Flag any file conflicts. If none, omit this section entirely.]

### Uncommitted Changes
[If any beyond what handoffs describe — otherwise omit]

### Last Session Summary
[Always present — 2 sentences from Step 6c JSONL analysis. Include turn count and MB. What we were working on + how the session ended. e.g. "We were building the tutorial video image sequencing for AuthorAware across 214 turns (11MB). The session ended abruptly — no terminate detected, likely a computer restart."]

### Terminate Check
[Always present — one of:
✅ Terminate ran — handoff written cleanly
⚠️ No terminate detected — session ended without handoff (window closed, crash, restart, or power loss)
🚨 Large session (N turns) ended without terminate — significant work has no handoff]

### Stopped Mid-Task
[If any handoff has a "Stopped Mid-Task" field — surface it HERE. Exact task, where it was left, what to do first.]

### Pending (combined)
[Merge pending items from all sessions into one list, deduped]

### Key Reminders
[Any feedback memories that apply — budget discipline, git workflow, etc.]

### Active Problem (crash recovery)
[What the code diffs + logs reveal was actively being worked on — feature/bug, completion state, likely next action. Always show this section.]

### Continue which session?
[If multiple sessions: list them by letter/name and ask the user to pick. e.g. "Session A (audiobook), Session B (Console Continuity), or start fresh?"]
```

Keep it tight. The user wants to glance at this and know exactly where things stand.

### Step 8: Start the workspace (server only)

After presenting the briefing, start the paperHTML server. This is the standard startup for the a-i-rons_projects parent repo.

**Confirmed paper server:** `scripts/paper_server.py` run from the repo root. This is the correct one — it serves all papers, the paper map, and notes/ content. Do NOT use paperHTML/serve.py (that is the Studio app), ai-companion/serve.py, or any other serve.py.

**Always kill and restart the server.** Do NOT open browser tabs automatically — not the paper map, not the daily brief archive.

```bash
# Kill any running instance on 8600
netstat -ano | grep ":8600 " | grep LISTEN | awk '{print $5}' | xargs -I{} cmd //c "taskkill /PID {} /F" 2>/dev/null

# Start paper_server.py from project root
cd /c/Users/aaron/Documents/a-i-rons_projects && python scripts/paper_server.py &

# Wait for it to be ready
sleep 2 && curl -s -o /dev/null -w "%{http_code}" http://localhost:8600/health
```

The daily brief runs automatically at 10:00 AM PST via Windows Task Scheduler (task: AaronDailyBrief). Do not run it from initiate. Do not open it in the browser. Links are available if needed:
- Paper map: http://localhost:8600/notes/paper-map-v3.html
- Daily brief archive: http://localhost:8600/notes/daily-brief.html

**Also check api-dash** — the spend monitor and circuit breaker should be running during every session:

```bash
curl -s --max-time 2 http://localhost:3737/api/spend > /dev/null 2>&1 && echo "api-dash ✓" || (cd /c/Users/aaron/Documents/a-i-rons_projects/api-dash && npm start & sleep 3 && echo "api-dash launched on http://localhost:3737")
```

Add `api-dash ✓` or `api-dash launched` to the briefing under **Model**.

### Step 9: Update your session state file

After presenting the briefing, update your session state file with the actual task you're starting (now that you know what it is from the handoff). Overwrite the file you created in Step 0.5:

```bash
echo "instance: session-<your-timestamp>
started: <start-time>
repo: <repo-name>
working-on: <first task from briefing>
files-active: (updating as work begins)
last-action: $(date '+%Y-%m-%d %H:%M')" > scripts/active-sessions/session-<your-timestamp>.md
```

Update `working-on` and `files-active` as your focus shifts during the session. This is the signal other instances will read.
