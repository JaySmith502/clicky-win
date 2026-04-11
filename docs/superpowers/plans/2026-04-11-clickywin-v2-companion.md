# ClickyWin v2 — Cursor Companion Implementation Plan

**Created:** 2026-04-11
**PRD:** `docs/PRD-v2-cursor-companion.md`
**Base tag:** `clickywin-v1.0.0` (commit `f72befe`)
**Branch:** `main` (direct, same as v1)

---

## Slice 1: Static companion follows cursor

### Task 1.1: Companion positioning logic [TDD]

**Files:**

- Create: `clicky-py/clicky/ui/companion_position.py`
- Create: `clicky-py/tests/test_companion_position.py`

**Steps:**

- [ ] **Step 1:** Write failing tests in `test_companion_position.py` covering:
  - Cursor at (500, 500) on 1920x1080 screen → position below-right with 20px offset
  - Cursor within 80px of right edge → flips to left side
  - Cursor within 80px of bottom edge → flips above
  - Cursor near bottom-right corner → flips both axes
  - Cursor on second monitor (offset geometry) → position stays on same screen
  - Companion dimensions parameter affects offset calculations
  - Dead zone: cursor moves <3px from last position → returns same position (no update)

- [ ] **Step 2:** Run tests. Expect fail.

- [ ] **Step 3:** Implement `companion_position.py`:
  - `@dataclass(frozen=True, slots=True) class CompanionPlacement(x: int, y: int, flipped_x: bool, flipped_y: bool)`
  - `compute_position(cursor_x: int, cursor_y: int, screen_rect: tuple[int, int, int, int], companion_size: tuple[int, int], offset: int = 20, edge_margin: int = 80) -> CompanionPlacement`
  - `should_update(prev_x: int, prev_y: int, cur_x: int, cur_y: int, dead_zone: int = 3) -> bool`

- [ ] **Step 4:** Run tests. Expect pass.

- [ ] **Step 5:** Commit:
  ```
  feat(clicky-py): add companion positioning logic with edge-flip
  ```

---

### Task 1.2: Companion widget — idle triangle overlay [IMPL]

**Files:**

- Create: `clicky-py/clicky/ui/companion_widget.py`

**Steps:**

- [ ] **Step 1:** Create `companion_widget.py` — a QWidget subclass:
  - Window flags: `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool`
  - Attributes: `WA_TranslucentBackground`, `WA_ShowWithoutActivating`
  - Fixed size: 80x40 (enough for triangle + future waveform expansion)
  - `paintEvent`: draw a 14px equilateral triangle pointing right, filled `#4a9eff` at 60% opacity
  - `_cursor_timer`: QTimer at 33ms interval (~30fps), calls `_track_cursor()`
  - `_track_cursor()`: get `QCursor.pos()`, find screen via `QApplication.screenAt()`, call `compute_position()`, move widget if `should_update()` returns True
  - `show()` override: start cursor timer. `hide()` override: stop timer.
  - No interaction — `setAttribute(Qt.WA_TransparentForMouseEvents, True)`

- [ ] **Step 2:** Wire into `app.py` temporarily for visual testing:
  - After creating QApplication, instantiate CompanionWidget and show it
  - Keep existing panel running in parallel
  - Verify: triangle appears, follows cursor, flips at screen edges

- [ ] **Step 3:** Commit:
  ```
  feat(clicky-py): add companion widget with cursor-following idle triangle
  ```

---

## Slice 2: Listening state + diamond waveform

### Task 2.1: Diamond waveform bar calculator [TDD]

**Files:**

- Create: `clicky-py/clicky/ui/waveform_bars.py`
- Create: `clicky-py/tests/test_waveform_bars.py`

**Steps:**

- [ ] **Step 1:** Write failing tests in `test_waveform_bars.py` covering:
  - RMS level 1.0 with max_height 20 → heights are `[10, 14, 18, 20, 20, 18, 14, 10]` (multipliers × max_height)
  - RMS level 0.0 → all bars at min_height (e.g., 2px)
  - RMS level 0.5 → proportionally scaled between min and max
  - Always returns exactly 8 values
  - Multipliers match diamond shape: `[0.5, 0.7, 0.9, 1.0, 1.0, 0.9, 0.7, 0.5]`

- [ ] **Step 2:** Run tests. Expect fail.

- [ ] **Step 3:** Implement `waveform_bars.py`:
  - `DIAMOND_WEIGHTS: tuple[float, ...] = (0.5, 0.7, 0.9, 1.0, 1.0, 0.9, 0.7, 0.5)`
  - `BAR_COUNT: int = 8`
  - `compute_bar_heights(rms: float, max_height: float, min_height: float = 2.0) -> list[float]`

- [ ] **Step 4:** Run tests. Expect pass.

- [ ] **Step 5:** Commit:
  ```
  feat(clicky-py): add diamond waveform bar height calculator
  ```

---

### Task 2.2: Companion listening state with waveform [IMPL]

**Files:**

- Modify: `clicky-py/clicky/ui/companion_widget.py`
- Modify: `clicky-py/clicky/ui/design_system.py`

**Steps:**

- [ ] **Step 1:** Add state colors to `design_system.py`:
  ```python
  # Companion state colors
  companion_idle = "#4a9eff"       # blue
  companion_listening = "#4a9eff"  # blue (same, opacity changes)
  companion_processing = "#f5a623" # amber
  companion_responding = "#34d399" # green
  companion_error = "#ef4444"      # red
  ```

- [ ] **Step 2:** Add to `companion_widget.py`:
  - Import `VoiceState` and `compute_bar_heights`
  - `set_state(state: VoiceState)` method — stores state, triggers repaint and animation
  - `set_audio_level(level: float)` method — stores RMS, triggers repaint when LISTENING
  - On LISTENING: triangle scales to 18px, full opacity. Paint 8 waveform bars to the right of triangle using `compute_bar_heights()`. Bars are rounded rects, colored companion_listening.
  - Idle→Listening transition: use `QPropertyAnimation` on custom `_scale` and `_opacity` properties, 150ms OutCubic
  - Listening→Idle transition: 300ms InCubic, waveform fades, triangle shrinks
  - Waveform repaint at 30fps (reuse cursor timer when LISTENING, or separate 33ms timer for audio-driven repaints)

- [ ] **Step 3:** Wire in `app.py`:
  - Connect `manager.state_changed` → `companion.set_state()`
  - Connect `manager.audio_level` → `companion.set_audio_level()`

- [ ] **Step 4:** Test manually: hold Ctrl+Alt, verify diamond waveform appears and reacts to voice. Release, verify smooth fade back to idle triangle.

- [ ] **Step 5:** Commit:
  ```
  feat(clicky-py): add listening state with diamond waveform to companion
  ```

---

## Slice 3: Full state color cycle + freeze

### Task 3.1: Processing + responding + error states [IMPL]

**Files:**

- Modify: `clicky-py/clicky/ui/companion_widget.py`

**Steps:**

- [ ] **Step 1:** Add PROCESSING state rendering:
  - Waveform bars morph to a single pulsing circle/dot, amber color
  - Pulse animation: QPropertyAnimation on `_pulse_scale` property, 0.8→1.2 looping, 600ms period
  - Transition from LISTENING: 200ms crossfade

- [ ] **Step 2:** Add RESPONDING state rendering:
  - Pulse dot changes to green, or gentle breathing animation
  - **Freeze positioning:** when entering RESPONDING, stop `_track_cursor()` updates (companion stays where it was). Resume on exit to IDLE.
  - Transition: 200ms color crossfade from amber→green

- [ ] **Step 3:** Add ERROR handling:
  - `flash_error()` method: briefly set color to red, hold 1 second, then fade back to idle state over 300ms
  - Connect `manager.error` signal to `companion.flash_error()`

- [ ] **Step 4:** Add any→IDLE transitions:
  - From PROCESSING/RESPONDING: pulse stops, color fades to blue, opacity to 60%, 300ms InCubic
  - Resume cursor tracking

- [ ] **Step 5:** Test manually: full voice turn, verify blue→amber→green→blue. Disable wifi, verify red flash. Interrupt mid-TTS, verify clean reset.

- [ ] **Step 6:** Commit:
  ```
  feat(clicky-py): add processing, responding, and error states to companion
  ```

---

## Slice 4: History window + tray simplification

### Task 4.1: History window [IMPL]

**Files:**

- Create: `clicky-py/clicky/ui/history_window.py`

**Steps:**

- [ ] **Step 1:** Create `history_window.py` — a QWidget subclass:
  - Normal window (not frameless, not overlay), resizable
  - Title: "ClickyWin — History"
  - Dark theme: background `#1a1a1a`, text `#e0e0e0` (reuse design tokens)
  - Minimum size: 400x300
  - Layout: QVBoxLayout with a QScrollArea containing a QVBoxLayout of turn widgets
  - Each turn: a QFrame with user text (labeled "You:") and assistant text (labeled "Clicky:")
  - User text: `#888888` (dimmer), assistant text: `#e0e0e0` (bright)

- [ ] **Step 2:** Add live-tail methods:
  - `append_interim(text: str)` — update current in-progress user line (italic, gray)
  - `set_final(text: str)` — finalize current user line
  - `append_delta(text: str)` — append to current in-progress assistant response
  - `commit_turn()` — finalize current turn, scroll to bottom
  - `show_error(msg: str)` — append red error line
  - Auto-scroll to bottom on each update (unless user has manually scrolled up)

- [ ] **Step 3:** Add to `app.py` — instantiate but don't show. Opened from tray menu.

- [ ] **Step 4:** Commit:
  ```
  feat(clicky-py): add live-tail history window
  ```

---

### Task 4.2: Tray simplification [IMPL]

**Files:**

- Modify: `clicky-py/clicky/ui/tray_icon.py`
- Modify: `clicky-py/clicky/app.py`

**Steps:**

- [ ] **Step 1:** Simplify `tray_icon.py`:
  - Remove state color changes (static icon only)
  - Remove model picker from context menu
  - Menu items: **Settings** (opens config.toml via `os.startfile`), **Show History** (emits signal), **Quit** (emits signal)
  - Add `show_history_requested` signal

- [ ] **Step 2:** Wire in `app.py`:
  - Connect `tray.show_history_requested` → `history_window.show()` / `history_window.raise_()`
  - Connect CompanionManager signals to history window:
    - `manager.interim_transcript` → `history.append_interim()`
    - `manager.final_transcript` → `history.set_final()`
    - `manager.response_delta` → `history.append_delta()`
    - `manager.response_complete` → `history.commit_turn()`
    - `manager.error` → `history.show_error()`
  - Remove `manager.state_changed` → old `tray_icon.set_state()` connection
  - Remove model picker signal connection

- [ ] **Step 3:** Test manually: right-click tray → Settings opens config.toml, Show History opens window, voice turn appears live in history, Quit exits.

- [ ] **Step 4:** Commit:
  ```
  feat(clicky-py): simplify tray to settings, history, quit
  ```

---

## Slice 5: Old UI removal

### Task 5.1: Remove deprecated panel and components [IMPL]

**Files:**

- Delete: `clicky-py/clicky/ui/panel.py`
- Delete: `clicky-py/clicky/ui/transcript_view.py`
- Delete: `clicky-py/clicky/ui/response_view.py`
- Delete: `clicky-py/clicky/ui/model_picker.py`
- Delete: `clicky-py/clicky/ui/status_banner.py`
- Delete: `clicky-py/clicky/ui/permissions_indicator.py`
- Modify: `clicky-py/clicky/ui/__init__.py` (if exists — clean exports)
- Modify: `clicky-py/clicky/app.py` (remove all panel references)
- Modify: `clicky-py/clicky/companion_manager.py` (remove PanelVisibilityController protocol)

**Steps:**

- [ ] **Step 1:** Remove all imports and references to deleted modules in `app.py`. Remove panel instantiation, panel signal connections, panel show/hide logic, click-outside dismissal.

- [ ] **Step 2:** Remove `PanelVisibilityController` protocol from `companion_manager.py`. The companion widget is tiny and transparent — verify whether mss captures it in screenshots. If yes, add a brief `companion.hide()` / `companion.show()` around screen capture. If no, remove hide-for-capture entirely.

- [ ] **Step 3:** Delete the six files listed above.

- [ ] **Step 4:** Run `uv run pytest` — all tests pass. Run `uv run ruff check .` — no lint errors.

- [ ] **Step 5:** Test manually: launch app, full voice turn works with only companion + history. No panel appears. Tray works.

- [ ] **Step 6:** Commit:
  ```
  refactor(clicky-py): remove deprecated panel and v1 UI components
  ```

---

## Execution rules (carried from v1)

- Work directly on `main` branch
- Commit after every task — use exact commit messages above
- STOP at every slice boundary for manual verification before proceeding
- Surface unexpected failures — don't silently work around
- Execute via `superpowers:subagent-driven-development`, one task at a time

---

## Test summary at plan completion

| Test file | Module tested | Test count |
|-----------|--------------|------------|
| `test_companion_position.py` | `compute_position`, `should_update` | 6-7 |
| `test_waveform_bars.py` | `compute_bar_heights` | 4-5 |
| (existing v1 tests) | config, transcription, SSE, screen labels, conversation, point parser | ~28 |
| **Total** | | **~40 tests** |
