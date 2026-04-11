# ClickyWin v2 — Cursor Companion Overlay

**Status:** Draft v2
**Date:** 2026-04-11
**Owner:** @JaySmith502
**Target release:** v2 (cursor companion overlay, history window, tray simplification)
**Depends on:** v1 (clickywin-v1.0.0) — all backend modules carry forward unchanged

---

## Problem Statement

ClickyWin v1 works: push-to-talk, screen capture, Claude streaming, TTS playback. But the UI is wrong for the product's core purpose. The 420x360 dark panel anchored near the system tray forces users to look away from their work to read text — yet ClickyWin is fundamentally a **voice companion**, not a text reading exercise. The panel was scaffolding for development, not the end-state UX.

Users need a minimal visual indicator that lives where they're already looking (near their cursor), communicates state without demanding attention, and gets out of the way. The text panel should only appear when explicitly requested — for accessibility, or to review what was said.

---

## Solution

Replace the anchored panel with a **cursor-following companion** — a small blue triangle that follows the mouse cursor at all times while ClickyWin is running. When the user holds Ctrl+Alt, the triangle wakes up: a compact 8-bar waveform expands from it, pulsing with their voice. On release, it shifts to amber (processing), then green (responding) while TTS plays. When TTS finishes, it fades back to its idle blue state.

The companion is the entire visible UI during normal use. For users who want to read text (hearing difficulties, noisy environments, review), a **history window** is available from the system tray — a scrollable, live-updating log of all conversation turns from the current session.

The system tray simplifies to three items: Settings (opens config.toml), Show History, and Quit.

---

## User Stories

1. As a Windows learner, I want a small visual indicator near my cursor so I know ClickyWin is running without checking the system tray.
2. As a Windows learner, I want the indicator to change when I hold Ctrl+Alt so I have immediate confirmation that ClickyWin heard me start talking.
3. As a Windows learner, I want to see my voice visualized as a compact waveform near my cursor so I know the mic is picking me up.
4. As a Windows learner, I want the companion to change color when processing so I know my question was sent and Claude is thinking.
5. As a Windows learner, I want the companion to change color when responding so I know TTS is actively playing my answer.
6. As a Windows learner, I want the companion to turn red briefly when an error occurs so I know something went wrong without a disruptive popup.
7. As a Windows learner, I want the companion to return to its idle state after TTS finishes so I know the turn is complete.
8. As a Windows learner, I want the companion to stop following my cursor during TTS playback so it doesn't distract me while I work and listen.
9. As a Windows learner, I want the companion to resume following my cursor after TTS completes.
10. As a Windows learner, I want the companion to flip sides when my cursor is near a screen edge so it never gets clipped off-screen.
11. As a Windows learner, I want the idle companion to be semi-transparent so it's visible but not distracting during long work sessions.
12. As a Windows learner, I want smooth animations when the companion transitions between states so the experience feels polished, not jarring.
13. As a hearing-impaired user, I want to open a history window from the tray that shows all conversation turns so I can read what was said.
14. As a hearing-impaired user, I want the history window to live-update as new turns come in so I can keep it open as a running transcript.
15. As a hearing-impaired user, I want the history window to show both my transcribed speech and Claude's responses so I have full context.
16. As a user in a noisy environment, I want to review what Claude said by opening the history window after a turn completes.
17. As a user, I want to access my config file from the tray menu so I can change settings without hunting for the file path.
18. As a user, I want to quit ClickyWin from the tray menu.
19. As a user, I want the tray icon to be static (no state colors) since the cursor companion now handles state indication.
20. As a developer configuring ClickyWin for a client, I want to set the model in config.toml so the end user doesn't need a model picker UI.
21. As a developer, I want the companion's positioning logic to be pure math (cursor position + screen bounds → widget position) so I can unit test it.
22. As a developer, I want the waveform renderer to accept RMS level and produce deterministic bar heights so I can test the diamond shape.
23. As a user on a multi-monitor setup, I want the companion to follow my cursor across screens without glitching at screen boundaries.
24. As a user, I want the waveform bars to form a diamond shape at full volume (center bars tallest, edges shortest) matching the Clicky/CursorBuddy visual style.
25. As a user, I want the companion to appear instantly when I launch ClickyWin — no loading screen or splash.

---

## Implementation Decisions

### Rendering Approach

Stay with Qt transparent top-level widget (QWidget with FramelessWindowHint + WA_TranslucentBackground + WindowStaysOnTopHint). No Electron, no QML. The companion is ~60px wide — QPainter handles this without jank.

**Optimization strategy:**
- Track cursor position via QTimer at 30fps (not 60 — idle indicator doesn't need 60fps)
- Only reposition window when cursor moves >3px from last position (skip no-ops)
- Only repaint on state change or audio level change — no constant redraw during idle
- During idle: no timer-driven repaints at all, just window repositioning

### Companion Widget States and Colors

| State | Color | Opacity | Visual |
|-------|-------|---------|--------|
| Idle | `#4a9eff` (blue) | 60% | Static 14px triangle, no animation |
| Listening | `#4a9eff` (blue) | 100% | Triangle scales to 18px, 8-bar waveform expands out (~60px wide) |
| Processing | `#f5a623` (amber) | 100% | Waveform morphs to pulsing dot/spinner |
| Responding | `#34d399` (green) | 100% | Gentle pulse or speaker glyph while TTS plays |
| Error | `#ef4444` (red) | 100% | Brief red flash, then fade back to idle |

### Waveform Specification

- 8 bars, diamond height multipliers: `[0.5, 0.7, 0.9, 1.0, 1.0, 0.9, 0.7, 0.5]`
- Total width: ~60px
- Bar height driven by RMS audio level (0.0–1.0) multiplied by per-bar weight
- Rounded rect bars with 2px corner radius (carried from v1)

### Companion Positioning

- Default: below-right of cursor, 20px offset
- Edge-flip: when cursor within 80px of right screen edge → flip to left; within 80px of bottom → flip above
- During RESPONDING state: companion freezes at position where response started; resumes cursor-following when TTS completes
- Multi-monitor: use QCursor.pos() (global coordinates), clamp to current screen geometry

### Animations

- Idle → Listening: triangle scales 14→18px, waveform slides out, ~150ms, OutCubic easing
- Listening → Processing: waveform contracts to pulse, ~200ms
- Processing → Responding: color crossfade, ~200ms
- Any → Idle: waveform fades out ~300ms, triangle shrinks to 14px, opacity to 60%, InCubic easing
- Use QPropertyAnimation on custom properties for smooth GPU-composited transitions

### History Window

- Normal resizable QWidget (not overlay, not frameless) — standard dark window
- Vertical scroll of alternating user/assistant blocks
- User blocks: show transcribed text, right-aligned or labeled
- Assistant blocks: show full response text, left-aligned or labeled
- Fed by existing ConversationHistory data structure
- Live-tail: connect to CompanionManager signals (final_transcript, response_complete) to append turns in real-time
- Opens centered on screen, not cursor-following
- Current session only — no cross-session persistence (v3 scope)

### Tray Menu

Three items only:
- **Settings** — `os.startfile(config_path)` to open config.toml in default editor
- **Show History** — opens/focuses history window
- **Quit** — exits application

Static tray icon, no state colors.

### Model Configuration

Model selection removed from UI entirely. Set via `default_model` in config.toml. Supported values: any Claude model ID (e.g., `claude-sonnet-4-6`). Future: may add non-Anthropic models. This is a developer/deployer concern, not an end-user runtime toggle.

### Signal Rewiring (app.py)

CompanionManager signals remain unchanged. Rewire targets:
- `state_changed` → `companion_widget.set_state()` (was panel)
- `audio_level` → `companion_widget.set_audio_level()` (was panel)
- `interim_transcript` → `history_window.append_interim()` (was panel.transcript)
- `final_transcript` → `history_window.set_final()` (was panel.transcript)
- `response_delta` → `history_window.append_delta()` (was panel.response)
- `response_complete` → `history_window.commit_turn()` (was panel.response)
- `error` → `companion_widget.flash_error()` + `history_window.show_error()` (was panel.banner)

### Modules Removed

- `ui/panel.py` — replaced by companion_widget
- `ui/transcript_view.py` — absorbed into history_window
- `ui/response_view.py` — absorbed into history_window
- `ui/model_picker.py` — removed, config-only
- `ui/status_banner.py` — replaced by companion error color
- `ui/permissions_indicator.py` — removed (was panel-embedded)

### Migration Strategy

Build companion_widget and history_window alongside existing panel. Wire both in parallel. Verify companion works. Then delete panel and related modules in a single cleanup commit.

---

## Testing Decisions

Good tests for this feature test **external behavior through public interfaces**, not internal painting details. We cannot screenshot-assert Qt widgets in CI, so tests focus on the pure logic extracted from rendering.

### Modules to Test

**1. Companion positioning logic** (`test_companion_positioning.py`)
- Given cursor position + screen bounds → assert widget position
- Test edge-flip: cursor near right edge → widget on left side
- Test edge-flip: cursor near bottom → widget above
- Test corner case: cursor near bottom-right → widget flips both axes
- Test multi-monitor: cursor on second screen → widget stays on same screen
- Test freeze during RESPONDING: position doesn't update when state is RESPONDING

**2. Diamond waveform bar heights** (`test_waveform_bars.py`)
- Given RMS level 1.0 → bar heights match diamond multipliers `[0.5, 0.7, 0.9, 1.0, 1.0, 0.9, 0.7, 0.5]` scaled to max height
- Given RMS level 0.0 → all bars at minimum height
- Given RMS level 0.5 → bars proportionally scaled
- Verify 8 bars always returned regardless of input

**Prior art:** `test_point_parser.py`, `test_screen_capture_labels.py` — same pattern of testing pure functions with known inputs/outputs.

### Modules NOT Tested

- History window — display-only, fed by signals, no logic worth unit testing
- Tray menu — 3 static items, trivial
- QPainter rendering — visual, not CI-testable
- Animation timings — subjective, tuned by eye

---

## Out of Scope

- **POINT tag overlay rendering** — parser exists (v1 Task 7.1), but drawing the cursor highlight on screen is v3
- **OpenAI / non-Anthropic providers** — LLMClient interface supports it, not wired
- **Streaming TTS** — current approach: full response → single TTS call. Chunked streaming is v3
- **Cross-session history persistence** — history window shows current session only
- **Settings GUI** — config.toml opened in editor, no custom settings dialog
- **Auto-update / installer** — still PyInstaller onedir, manual distribution
- **Custom companion skins/themes** — single blue triangle design
- **Voice commands** ("switch to Opus") — config-only model selection
- **Accessibility beyond history window** — screen reader support, high contrast mode are v3

---

## Further Notes

- The companion widget is the first piece of ClickyWin that will be visually distinctive from Farza's Clicky. The triangle-follows-cursor pattern is inspired by CursorBuddy but implemented in Qt, not Electron. This is where ClickyWin starts developing its own identity.
- The 30fps cursor tracking timer is a deliberate choice. 60fps doubles CPU cost for no perceptible difference on a 14px triangle. If users report jank, the timer interval is a single constant to change.
- The PanelVisibilityController protocol in CompanionManager (hide panel before screenshot) needs updating — the companion is tiny and transparent, so it likely doesn't need to hide for captures. But verify: does mss capture transparent Qt windows? If yes, the companion might appear in screenshots sent to Claude. May need to hide it briefly or exclude its region.
- Config.toml gains no new fields in v2. All companion behavior is hardcoded (colors, sizes, timings). Configurability is v3 scope creep.
