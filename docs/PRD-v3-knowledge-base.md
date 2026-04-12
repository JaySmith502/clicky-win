# ClickyWin v3 — Screen-Aware Knowledge Base

**Status:** Draft v3
**Date:** 2026-04-12
**Owner:** @JaySmith502
**Target release:** v3 (local KB injection based on active window)
**Depends on:** v2.1 (clickywin-v2.1.0) — companion, POINT tags, screen capture

---

## Problem Statement

Claude's training data is thin on niche software — Wild Apricot, industry ERPs, internal SOPs, specialty creative tools. When a user asks ClickyWin for help with one of these apps, Claude can see the screen but doesn't know HOW to use the software. It guesses based on UI patterns, which is often wrong or vague. The user needs ClickyWin to be an expert on the specific software they're learning, not just a general-purpose vision model.

This is the core business problem: a consulting client (e.g. a nonprofit leader struggling with Wild Apricot) needs ClickyWin to be a knowledgeable trainer for THEIR specific tools, not a generalist that hallucinates menu paths.

---

## Solution

A local knowledge base of curated markdown documentation, organized by application. When the user presses push-to-talk, ClickyWin detects which application is in the foreground via the Windows API, matches it against KB folders, and injects the relevant documentation into Claude's system prompt alongside the existing voice/style/pointing rules. Claude then answers using authoritative reference material rather than guessing.

The KB is authored by the developer/consultant: gather the client's software documentation, distill it into focused markdown (via NotebookLM or manual curation), place it in a folder structure, and write a small metadata file mapping window titles to KB folders. No vector database, no embeddings, no cloud infrastructure — just markdown files on disk.

When no KB matches the active app, Claude answers as it does today — with training knowledge and screenshot context. A hint in the system prompt tells Claude when it does or doesn't have app-specific documentation, so it can calibrate its confidence.

---

## User Stories

1. As a Windows learner using Wild Apricot, I want ClickyWin to know the correct menu paths and terminology so it gives me accurate step-by-step guidance.
2. As a Windows learner, I want ClickyWin to automatically detect which app I'm asking about so I don't have to tell it what software I'm using.
3. As a Windows learner, I want ClickyWin to prioritize the curated documentation over its training data when they conflict so I get correct answers for my specific software version.
4. As a Windows learner switching between apps, I want ClickyWin to load the right KB per question so I get relevant help regardless of which app I switched to.
5. As a Windows learner using an app with no KB, I want ClickyWin to still answer helpfully using its training knowledge and what it sees on screen.
6. As a consultant deploying ClickyWin for a client, I want a simple folder structure for KB content so I can author and update it without tooling.
7. As a consultant, I want a metadata file per app that maps window titles to KB folders so I can support any software the client uses.
8. As a consultant, I want KB content to be plain markdown so I can generate it from any source (NotebookLM, manual writing, doc exports).
9. As a consultant, I want to add a new app's KB by creating a folder and a TOML file — no code changes, no restart required.
10. As a consultant, I want a token budget that automatically selects the most relevant sections when a KB is too large so I don't have to worry about prompt size.
11. As a consultant, I want the overview document to always be included so Claude has baseline context about the app even when section selection kicks in.
12. As a developer, I want the KB directory to be configurable in config.toml so different deployments can point to different knowledge sets.
13. As a developer, I want ClickyWin to work normally when no KB directory exists or is empty — no errors, no degraded experience.
14. As a developer, I want the app matching and section selection logic to be pure functions I can unit test without touching the filesystem.
15. As a developer, I want KB loading to happen per turn so the user can switch apps between questions without restarting.
16. As a Windows learner, I want Claude to tell me when it has specific documentation loaded versus when it's working from general knowledge so I can calibrate my trust in the answer.

---

## Implementation Decisions

### KB Folder Structure

```
%APPDATA%/ClickyWin/knowledge/
  ├── wild_apricot/
  │   ├── _meta.toml
  │   ├── overview.md
  │   ├── events.md
  │   ├── membership.md
  │   └── donations.md
  └── davinci_resolve/
      ├── _meta.toml
      ├── overview.md
      └── color_grading.md
```

Each app gets a subfolder. The `_meta.toml` file maps window titles to this KB:

```toml
name = "Wild Apricot"
window_titles = ["Wild Apricot"]
```

`overview.md` is the always-included baseline document. All other `.md` files are selectable sections.

### Config Extension

Add optional field to `config.toml`:

```toml
knowledge_dir = "C:/path/to/knowledge"
```

Default: `%APPDATA%/ClickyWin/knowledge/`. If the directory doesn't exist or is empty, KB injection is silently skipped.

### Active Window Detection

Use Win32 API (`ctypes.windll.user32.GetForegroundWindow` + `GetWindowTextW`) to read the foreground window title on each hotkey release. This is a single syscall, <1ms.

### App Matching

Case-insensitive substring match: if the foreground window title contains any string from a KB folder's `window_titles` list, that folder is selected. First match wins. Scan is O(n) over KB folders — negligible even with 20+ folders.

### Content Selection and Token Budget

Character-based token approximation: `len(content) // 4` ≈ token count. Budget cap: 60,000 characters (~15k tokens).

**If total KB content for matched app fits under budget:** include all markdown files.

**If over budget:**
1. Always include `overview.md` (never skipped, subtracted from budget)
2. Extract headings from remaining `.md` files (lines starting with `#`)
3. Tokenize user transcript into keywords (lowercase, strip ~30 hardcoded stop words)
4. Score each file by keyword overlap count between its headings and the transcript
5. Include files in descending score order until budget exhausted
6. Tie-break by file size (smaller first — fit more sections)

### System Prompt Construction

Dynamic per turn. When KB matches:

```
[existing voice/style/pointing rules]

app knowledge base:
you are helping the user with [App Name]. here is reference documentation that you should treat as authoritative:

[overview.md content]

[selected sections]
```

When no KB matches:

```
[existing voice/style/pointing rules]

no app-specific knowledge base is loaded for this session. answer based on your training knowledge and what you can see on screen.
```

### Pipeline Integration

In CompanionManager, per turn (after hotkey release, before LLM request):
1. Get foreground window title via active_window module
2. Pass title + user transcript to knowledge_base module
3. Receive matched app name + selected content (or None)
4. Build system prompt string with or without KB content
5. Pass to LLM client (replaces the static `COMPANION_VOICE_SYSTEM_PROMPT` constant)

### Per-Turn Loading, No Cache

KB files are read from disk on every turn. Markdown files are small (<100KB typical), disk reads take <10ms. No caching needed. This ensures the user gets fresh content if the consultant updates KB files while ClickyWin is running.

---

## Testing Decisions

Good tests for this feature test the matching and selection logic through pure function interfaces, using in-memory data structures rather than real filesystem access.

### Modules to Test

**1. Knowledge base matching and selection** (`test_knowledge_base.py`)

Core functions accept parsed data structures, not file paths, so tests don't touch disk:

- Window title "Wild Apricot - Events" matches KB with `window_titles = ["Wild Apricot"]`
- Window title "Google Chrome" with no matching KB → returns None
- Case-insensitive matching: "WILD APRICOT" matches "Wild Apricot"
- Multiple KB folders, first match wins
- Small KB under budget → all content returned
- Large KB over budget → overview always included, sections selected by transcript keyword overlap
- User says "how do I add an event" → `events.md` with heading "Adding Events" scores highest
- Empty transcript → only overview included (no keyword signal)
- KB folder with only `_meta.toml` and `overview.md` → overview returned, no error
- KB folder with no `overview.md` → all files treated as selectable sections

**Prior art:** `test_companion_position.py`, `test_point_mapper.py` — same pattern of testing pure functions with known inputs.

### Modules NOT Tested

- Active window detection — single Win32 syscall, platform-specific, not unit-testable
- System prompt assembly — string concatenation, verified via manual smoke test
- CompanionManager integration — orchestration, manual verification
- Config field addition — trivial, existing config tests cover the pattern

---

## Out of Scope

- **Online discovery / web search** — Claude searching the web when no KB exists is a separate feature (v3.1)
- **Automatic KB generation** — no auto-crawling docs or auto-distilling. KB is manually authored by the consultant.
- **Vector embeddings / RAG** — heading-based keyword matching is sufficient for the KB sizes involved (30-80 pages per app)
- **OCR of screen text** — matching is done via window title only, not screen content
- **KB editing UI** — consultant edits markdown files directly, no GUI
- **KB sharing / sync** — KB lives on local disk only. No cloud sync, no multi-user.
- **Multiple KB matches** — if the user has two apps open, only the foreground app's KB is loaded. No merging across KBs.
- **exe_name matching** — the `_meta.toml` format reserves space for `exe_names` but this PRD only implements `window_titles` matching. Process-level detection is v3.1.

---

## Further Notes

- This is the consulting revenue play. The KB is what transforms ClickyWin from a novelty into a deployable training tool worth $2-5k setup per client.
- NotebookLM is the recommended authoring tool but not a dependency. Any process that produces markdown works — manual writing, doc exports, ChatGPT summarization, copy-paste from help sites.
- The ~15k token budget for KB content is conservative. Claude's context window is much larger, but we're sharing it with screenshots (base64 JPEGs are ~10-20k tokens per image), conversation history, and the system prompt. 15k keeps KB from crowding out the visual context that makes ClickyWin useful.
- The "treat as authoritative" framing in the system prompt is deliberate. Without it, Claude sometimes ignores injected docs in favor of its training data, especially when the training data is confidently wrong about niche software.
- Per-turn loading with no cache means the consultant can hot-reload KB content by editing files while ClickyWin runs. Useful during initial KB authoring and testing.
