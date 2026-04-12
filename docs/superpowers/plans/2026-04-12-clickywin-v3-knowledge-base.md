# ClickyWin v3 — Knowledge Base Implementation Plan

**Created:** 2026-04-12
**PRD:** `docs/PRD-v3-knowledge-base.md`
**Base tag:** `clickywin-v2.1.0` (commit `63840b1`)
**Branch:** `main` (direct)

---

## Slice 1: KB matching + section selection TDD

### Task 1.1: KB matching and section selection [TDD]

**Files:**

- Create: `clicky-py/clicky/knowledge_base.py`
- Create: `clicky-py/tests/test_knowledge_base.py`

**Steps:**

- [ ] **Step 1:** Write failing tests in `test_knowledge_base.py`. Core functions accept parsed data, not file paths:

  Data structures for testing:
  ```python
  @dataclass
  class KBApp:
      name: str
      window_titles: list[str]
      overview: str  # overview.md content
      sections: list[tuple[str, str]]  # (filename, content) for each .md file

  # Functions under test:
  # match_app(window_title: str, apps: list[KBApp]) -> KBApp | None
  # select_content(app: KBApp, transcript: str, budget_chars: int = 60000) -> str
  ```

  Test cases for `match_app`:
  - "Wild Apricot - Events" matches KBApp with `window_titles=["Wild Apricot"]` → returns that app
  - "Google Chrome" with no matching KB → returns None
  - Case-insensitive: "WILD APRICOT" matches "Wild Apricot"
  - Multiple apps, first match wins
  - Empty app list → returns None

  Test cases for `select_content`:
  - Small KB under budget → returns overview + all sections concatenated
  - Large KB over budget → overview always included, sections selected by transcript keyword overlap
  - User says "how do I add an event" with sections ["events.md" with heading "## Adding Events", "membership.md" with heading "## Managing Members"] → events.md scores higher
  - Empty transcript → only overview returned
  - KB with only overview → overview returned, no error

- [ ] **Step 2:** Run tests. Expect fail.

- [ ] **Step 3:** Implement `knowledge_base.py`:

  ```python
  STOP_WORDS = frozenset({
      "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
      "have", "has", "had", "do", "does", "did", "will", "would", "could",
      "should", "may", "might", "can", "shall", "i", "me", "my", "we",
      "you", "your", "it", "its", "this", "that", "how", "what", "where",
      "when", "why", "which", "who", "in", "on", "at", "to", "for", "of",
      "with", "by", "from", "and", "or", "not", "no", "but", "if", "so",
      "just", "about", "up", "out", "into",
  })

  @dataclass
  class KBApp:
      name: str
      window_titles: list[str]
      overview: str
      sections: list[tuple[str, str]]  # (filename, content)

  def match_app(window_title: str, apps: list[KBApp]) -> KBApp | None:
      title_lower = window_title.lower()
      for app in apps:
          for wt in app.window_titles:
              if wt.lower() in title_lower:
                  return app
      return None

  def _extract_keywords(text: str) -> set[str]:
      words = set(text.lower().split())
      return words - STOP_WORDS

  def _extract_headings(content: str) -> str:
      return " ".join(
          line.lstrip("#").strip()
          for line in content.splitlines()
          if line.startswith("#")
      )

  def _score_section(headings_text: str, keywords: set[str]) -> int:
      heading_words = set(headings_text.lower().split())
      return len(heading_words & keywords)

  def select_content(
      app: KBApp, transcript: str, budget_chars: int = 60_000
  ) -> str:
      parts = [f"## {app.name} — Overview\n\n{app.overview}"]
      remaining = budget_chars - len(app.overview)

      if not app.sections:
          return "\n\n".join(parts)

      # Check if everything fits
      total_sections = sum(len(c) for _, c in app.sections)
      if total_sections <= remaining:
          for filename, content in app.sections:
              parts.append(content)
          return "\n\n".join(parts)

      # Over budget — rank by keyword overlap with transcript
      keywords = _extract_keywords(transcript)
      scored = []
      for filename, content in app.sections:
          headings = _extract_headings(content)
          score = _score_section(headings, keywords)
          scored.append((score, len(content), filename, content))

      # Sort: highest score first, then smallest file first (fit more)
      scored.sort(key=lambda t: (-t[0], t[1]))

      for score, size, filename, content in scored:
          if size <= remaining:
              parts.append(content)
              remaining -= size

      return "\n\n".join(parts)
  ```

- [ ] **Step 4:** Run tests. Expect pass.

- [ ] **Step 5:** Commit:
  ```
  feat(clicky-py): add KB matching and section selection with TDD
  ```

---

## Slice 2: Active window detection + config

### Task 2.1: Active window detection [IMPL]

**Files:**

- Create: `clicky-py/clicky/active_window.py`

**Steps:**

- [ ] **Step 1:** Create `active_window.py`:
  ```python
  """Active window title detection via Win32 API."""

  from __future__ import annotations

  import ctypes
  import logging

  logger = logging.getLogger(__name__)


  def get_foreground_window_title() -> str:
      """Return the title of the current foreground window.

      Returns empty string if detection fails.
      """
      try:
          hwnd = ctypes.windll.user32.GetForegroundWindow()
          length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
          if length == 0:
              return ""
          buf = ctypes.create_unicode_buffer(length + 1)
          ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
          return buf.value
      except Exception:  # noqa: BLE001
          logger.debug("failed to get window title", exc_info=True)
          return ""
  ```

- [ ] **Step 2:** Commit:
  ```
  feat(clicky-py): add active window title detection via Win32
  ```

---

### Task 2.2: Config knowledge_dir + filesystem KB loader [IMPL]

**Files:**

- Modify: `clicky-py/clicky/config.py`
- Modify: `clicky-py/config.example.toml`
- Add: filesystem loading functions to `clicky-py/clicky/knowledge_base.py`

**Steps:**

- [ ] **Step 1:** Add `knowledge_dir` field to Config dataclass. Optional, defaults to `%APPDATA%/ClickyWin/knowledge/`. If the directory doesn't exist, set to None — no error.

- [ ] **Step 2:** Add `knowledge_dir` to `config.example.toml` with a comment:
  ```toml
  # Path to knowledge base folder. Each subfolder = one app's KB.
  # Default: %APPDATA%/ClickyWin/knowledge/
  # knowledge_dir = "C:/path/to/knowledge"
  ```
  (Commented out — uses default unless overridden.)

- [ ] **Step 3:** Add filesystem loader to `knowledge_base.py`:
  ```python
  def load_kb_from_disk(knowledge_dir: Path) -> list[KBApp]:
      """Scan knowledge_dir for app KB folders. Returns list of KBApp."""
  ```
  - Scan subdirectories of knowledge_dir
  - Each subdir must have `_meta.toml` — skip if missing
  - Parse `_meta.toml` for `name` and `window_titles`
  - Read `overview.md` if present (empty string if not)
  - Read all other `.md` files as sections
  - Return list of KBApp

- [ ] **Step 4:** Run tests + lint.

- [ ] **Step 5:** Commit:
  ```
  feat(clicky-py): add knowledge_dir config and KB filesystem loader
  ```

---

## Slice 3: Pipeline wiring + dynamic system prompt

### Task 3.1: Dynamic system prompt builder [IMPL]

**Files:**

- Modify: `clicky-py/clicky/prompts.py`

**Steps:**

- [ ] **Step 1:** Convert `COMPANION_VOICE_SYSTEM_PROMPT` from a constant to be used by a builder function:
  ```python
  _BASE_PROMPT = """..."""  # existing prompt text (rename the constant)

  def build_system_prompt(kb_content: str | None = None, app_name: str | None = None) -> str:
      """Build the full system prompt, optionally with KB content."""
      parts = [_BASE_PROMPT]
      if kb_content and app_name:
          parts.append(
              f"\napp knowledge base:\n"
              f"you are helping the user with {app_name}. "
              f"here is reference documentation that you should treat as authoritative:\n\n"
              f"{kb_content}"
          )
      else:
          parts.append(
              "\nno app-specific knowledge base is loaded for this session. "
              "answer based on your training knowledge and what you can see on screen."
          )
      return "\n".join(parts)
  ```

- [ ] **Step 2:** Commit:
  ```
  feat(clicky-py): add dynamic system prompt builder with KB injection
  ```

---

### Task 3.2: Wire KB into CompanionManager turn pipeline [IMPL]

**Files:**

- Modify: `clicky-py/clicky/companion_manager.py`

**Steps:**

- [ ] **Step 1:** Add imports:
  ```python
  from clicky.active_window import get_foreground_window_title
  from clicky.knowledge_base import load_kb_from_disk, match_app, select_content
  from clicky.prompts import build_system_prompt
  ```

- [ ] **Step 2:** In `__init__`, store knowledge_dir from config:
  ```python
  self._knowledge_dir = config.knowledge_dir  # Path | None
  ```

- [ ] **Step 3:** In `_run_turn`, before the LLM request (before `self._set_state(VoiceState.RESPONDING)`):
  ```python
  # Detect active app and load KB
  window_title = get_foreground_window_title()
  kb_content = None
  app_name = None
  if self._knowledge_dir is not None:
      apps = load_kb_from_disk(self._knowledge_dir)
      matched = match_app(window_title, apps)
      if matched is not None:
          app_name = matched.name
          kb_content = select_content(matched, text)
          logger.info("KB loaded: %s (%d chars)", app_name, len(kb_content))

  system_prompt = build_system_prompt(kb_content, app_name)
  ```

- [ ] **Step 4:** Replace the static `COMPANION_VOICE_SYSTEM_PROMPT` in the `self._llm.send()` call with `system_prompt`.

- [ ] **Step 5:** Remove the direct import of `COMPANION_VOICE_SYSTEM_PROMPT` (replaced by `build_system_prompt`).

- [ ] **Step 6:** Run all tests + lint.

- [ ] **Step 7:** Commit:
  ```
  feat(clicky-py): wire KB into turn pipeline with per-turn loading
  ```

---

## Slice 4: Sample KB + smoke test

### Task 4.1: Create sample KB and end-to-end test [HITL]

**Files:**

- Create: sample KB folder (user chooses app)

**Steps:**

- [ ] **Step 1:** User decides which app to create a sample KB for (DaVinci Resolve, Wild Apricot, or another app they have installed).

- [ ] **Step 2:** Create KB folder structure:
  ```
  %APPDATA%/ClickyWin/knowledge/<app_name>/
    ├── _meta.toml
    ├── overview.md
    └── <topic>.md (2-3 section files)
  ```

- [ ] **Step 3:** Write `_meta.toml` with window title matchers for the chosen app.

- [ ] **Step 4:** Write `overview.md` — 2-3 paragraph overview of the app and its key concepts.

- [ ] **Step 5:** Write 2-3 topic `.md` files with headings and concise how-to content.

- [ ] **Step 6:** Smoke test:
  - Open the target app
  - Ask ClickyWin a question about it → verify Claude references KB content
  - Ask a follow-up → verify context carries through
  - Switch to an app without KB → verify normal response
  - Ask a general knowledge question → verify no KB interference

- [ ] **Step 7:** Commit sample KB if it should ship with the repo, or leave as local-only.

---

## Execution rules (carried from v1/v2)

- Work directly on `main` branch
- Commit after every task — use exact commit messages above
- STOP at every slice boundary for manual verification before proceeding
- Surface unexpected failures — don't silently work around
- Slices 1 and 2 can be executed in parallel
- Slice 4 is HITL — user provides the sample app and verifies Claude's answers

---

## Test summary at plan completion

| Test file | Module tested | Test count |
|-----------|--------------|------------|
| `test_knowledge_base.py` | `match_app`, `select_content` | ~10 |
| (existing) | point_parser, point_mapper, positioning, waveform, config, etc. | ~60 |
| **Total** | | **~70 tests** |
