---
name: recall
description: Cross-project transcript search — find any prior exchange across all sessions and sub-repos
user-invocable: true
---

## Natural Language Triggers

This skill fires on plain English — no `/recall` command needed:

- "recall X"
- "find where we talked about X"
- "what did we say about X"
- "do you remember when we discussed X"
- "look up our conversation about X"
- "when did we do / build / decide X"
- "where did we land on X"

Extract the topic as the query. Run immediately — do not ask the user to rephrase as a command.

## Recall Procedure

The user wants to search their full conversation history across all projects.

### Step 1: Extract the query

The user's message after `/recall` is the search query. If no query provided, ask for one.

Examples:
- `/recall rejection memory` → query = "rejection memory"
- `/recall bi-temporal` → query = "bi-temporal"
- `/recall service layer` → query = "service layer"

### Step 2: Run the search

```bash
python /c/Users/aaron/Documents/a-i-rons_projects/scripts/recall.py "<query>"
```

If inside a sub-repo, use the absolute path above — the script lives in the parent repo.

Optional flags:
- `--limit 30` — show more results (default: 20)
- `--project ai-companion` — restrict to one sub-repo

### Step 3: Present results

**If L1 (session index) results found:**
Show the session blocks. These are human-written summaries from /terminate — high signal. Tell the user which session(s) the topic appeared in and offer to drill into the full transcript for any of them.

**If only L2 (raw transcript) results:**
Show the Q/A pairs. Each result includes project name and date. Offer to read the full JSONL around a specific result if the user wants more context:

```bash
python -c "
import json, sys
lines = open(sys.argv[1]).readlines()
for i, line in enumerate(lines):
    try:
        obj = json.loads(line)
        msg = obj.get('message', {})
        role = msg.get('role', '')
        content = msg.get('content', '')
        if isinstance(content, list):
            content = ' '.join(p.get('text','') for p in content if isinstance(p,dict) and p.get('type')=='text')
        if content.strip():
            print(f'[{role}] {content[:300]}')
            print('---')
    except: pass
" <jsonl_path> | head -100
```

**If no results:**
Say so plainly. Suggest alternate search terms. Do not invent results.

### Step 4: Offer drill-down

After showing results, offer:
- "Want me to read the full exchange from [project] on [date]?"
- "Want me to search for a related term?"

### Notes
- The search is case-insensitive
- L1 (session-index.md) is written by /terminate — grows over time as sessions are closed cleanly
- L2 is the raw JSONL — always complete, slightly slower to parse
- Results are sorted newest-first
