# ClickyWin v2.1 — Cursor Guidance Implementation Plan

**Created:** 2026-04-12
**PRD:** `docs/PRD-v2.1-cursor-guidance.md`
**Base tag:** `clickywin-v2.0.0` (commit `86e3d58`)
**Branch:** `main` (direct)

---

## Slice 1: Screenshot metadata + point mapper TDD

### Task 1.1: Enrich ScreenshotImage with capture metadata [IMPL]

**Files:**

- Modify: `clicky-py/clicky/screen_capture.py`

**Steps:**

- [ ] **Step 1:** Add fields to `ScreenshotImage` dataclass:
  - `scale: float` — downscale ratio applied (e.g. 0.667 for 1920→1280). 1.0 if no downscale.
  - `monitor_left: int` — global X origin of this monitor
  - `monitor_top: int` — global Y origin of this monitor

- [ ] **Step 2:** Populate the new fields in `capture_all()`. The scale and monitor offsets are already computed in the capture loop — just surface them:
  - `scale` = `_MAX_LONG_EDGE / long_edge` if downscaled, else `1.0`
  - `monitor_left` = `monitor["left"]` from mss
  - `monitor_top` = `monitor["top"]` from mss

- [ ] **Step 3:** Update `test_screen_capture_labels.py` if any tests construct ScreenshotImage directly — add the new fields.

- [ ] **Step 4:** Run `uv run pytest -v` and `uv run ruff check .`

- [ ] **Step 5:** Commit:
  ```
  feat(clicky-py): add scale and monitor offset to ScreenshotImage
  ```

---

### Task 1.2: Point coordinate mapper [TDD]

**Files:**

- Create: `clicky-py/clicky/point_mapper.py`
- Create: `clicky-py/tests/test_point_mapper.py`

**Steps:**

- [ ] **Step 1:** Write failing tests in `test_point_mapper.py` covering:
  - Single monitor: PointTag(640, 360) + screenshot(scale=0.667, monitor_left=0, monitor_top=0) → real coords (960, 540)
  - No downscale: PointTag(100, 200) + screenshot(scale=1.0, monitor_left=0, monitor_top=0) → (100, 200)
  - Multi-monitor offset: PointTag(100, 100) + screenshot(scale=0.5, monitor_left=1920, monitor_top=0) → (2120, 200)
  - Screen number: PointTag(50, 50, screen=2) + two screenshots → uses second screenshot's metadata
  - Out-of-range screen: PointTag(50, 50, screen=3) + two screenshots → falls back to first screenshot
  - No screen specified: PointTag(50, 50, screen=None) → uses first screenshot
  - Empty screenshot list → returns None

- [ ] **Step 2:** Run tests. Expect fail.

- [ ] **Step 3:** Implement `point_mapper.py`:
  ```python
  from clicky.point_parser import PointTag
  from clicky.screen_capture import ScreenshotImage

  def map_point_to_screen(
      tag: PointTag,
      screenshots: list[ScreenshotImage],
  ) -> tuple[int, int] | None:
      """Map POINT tag coordinates to real screen pixels."""
      if not screenshots:
          return None

      # Select target screenshot
      if tag.screen is not None and 1 <= tag.screen <= len(screenshots):
          shot = screenshots[tag.screen - 1]  # 1-indexed
      else:
          shot = screenshots[0]  # cursor's screen (first in list)

      real_x = shot.monitor_left + int(tag.x / shot.scale)
      real_y = shot.monitor_top + int(tag.y / shot.scale)
      return (real_x, real_y)
  ```

- [ ] **Step 4:** Run tests. Expect pass.

- [ ] **Step 5:** Commit:
  ```
  feat(clicky-py): add POINT tag coordinate mapper with TDD
  ```

---

## Slice 2: System prompt + POINT pipeline wiring

### Task 2.1: Add pointing section to system prompt [IMPL]

**Files:**

- Modify: `clicky-py/clicky/prompts.py`

**Steps:**

- [ ] **Step 1:** Append Farza's element-pointing section to `COMPANION_VOICE_SYSTEM_PROMPT`. Add after the existing rules, before the closing triple-quote:

  ```
  element pointing:
  you have a small blue triangle cursor that can fly to and point at things on screen. use it whenever pointing would genuinely help the user — if they're asking how to do something, looking for a menu, trying to find a button, or need help navigating an app, point at the relevant element. err on the side of pointing rather than not pointing, because it makes your help way more useful and concrete.

  don't point at things when it would be pointless — like if the user asks a general knowledge question, or the conversation has nothing to do with what's on screen, or you'd just be pointing at something obvious they're already looking at. but if there's a specific UI element, menu, button, or area on screen that's relevant to what you're helping with, point at it.

  when you point, append a coordinate tag at the very end of your response, AFTER your spoken text. the screenshot images are labeled with their pixel dimensions. use those dimensions as the coordinate space. the origin (0,0) is the top-left corner of the image. x increases rightward, y increases downward.

  format: [POINT:x,y:label] where x,y are integer pixel coordinates in the screenshot's coordinate space, and label is a short 1-3 word description of the element (like "search bar" or "save button"). if the element is on the cursor's screen you can omit the screen number. if the element is on a DIFFERENT screen, append :screenN where N is the screen number from the image label (e.g. :screen2). this is important — without the screen number, the cursor will point at the wrong place.

  if pointing wouldn't help, append [POINT:none].

  examples:
  - user asks how to color grade in davinci resolve: "you'll want to open the color page — it's that paintbrush-looking icon at the bottom of the screen. click that and you'll get all the color wheels and curves. [POINT:640,950:color page]"
  - user asks what html is: "html stands for hypertext markup language, it's basically the skeleton of every web page. curious how it connects to the css you're looking at? [POINT:none]"
  - user asks where the commit button is in vs code: "see that source control icon in the sidebar? it looks like a little branch. click that and you'll see the commit button right at the top. [POINT:24,180:source control]"
  - element is on screen 2 (not where cursor is): "that's over on your other monitor — see the terminal window? [POINT:400,300:terminal:screen2]"
  ```

  Note: Examples retargeted to Windows apps (DaVinci Resolve, VS Code) matching ClickyWin persona, not Farza's macOS examples.

- [ ] **Step 2:** Update the module docstring to note that the pointing section is now active.

- [ ] **Step 3:** Commit:
  ```
  feat(clicky-py): add element pointing section to system prompt
  ```

---

### Task 2.2: Wire POINT parsing into CompanionManager [IMPL]

**Files:**

- Modify: `clicky-py/clicky/companion_manager.py`
- Modify: `clicky-py/clicky/ui/companion_widget.py` (add stub `fly_to` that logs only — real animation in Slice 3)

**Steps:**

- [ ] **Step 1:** In `CompanionManager.__init__`, add instance variable to store current turn's screenshot metadata:
  ```python
  self._current_screenshots: list[ScreenshotImage] = []
  ```

- [ ] **Step 2:** In the capture phase of `_run_turn()`, store the screenshots:
  ```python
  self._current_screenshots = screenshots
  ```

- [ ] **Step 3:** After `response_complete` fires (in `_run_turn` after LLM streaming completes), add POINT parsing before TTS:
  - Import `parse_point_tag` and `map_point_to_screen`
  - `spoken_text, point_tag = parse_point_tag(full_response_text)`
  - If `point_tag` is not None: `coords = map_point_to_screen(point_tag, self._current_screenshots)`
  - If coords: call `self._capture_visibility_controller.fly_to(coords[0], coords[1])`
  - Send `spoken_text` (not `full_response_text`) to TTS

- [ ] **Step 4:** Add a stub `fly_to(x, y)` method to `CompanionWidget` that just logs:
  ```python
  def fly_to(self, x: int, y: int) -> None:
      """Animate to target position. Stub — animation added in Slice 3."""
      logger.info("fly_to: (%d, %d)", x, y)
  ```

- [ ] **Step 5:** Run all tests + lint. Verify no breakage.

- [ ] **Step 6:** Commit:
  ```
  feat(clicky-py): wire POINT tag parsing into response pipeline
  ```

---

## Slice 3: Companion fly-to + return animation

### Task 3.1: Implement fly_to and return_to_cursor [IMPL]

**Files:**

- Modify: `clicky-py/clicky/ui/companion_widget.py`

**Steps:**

- [ ] **Step 1:** Add QPropertyAnimation for position. In `__init__`:
  ```python
  self._pos_anim = QPropertyAnimation(self, b"pos")
  self._fly_target: tuple[int, int] | None = None  # where we flew to
  ```

- [ ] **Step 2:** Replace the stub `fly_to` with real animation:
  ```python
  def fly_to(self, x: int, y: int) -> None:
      """Animate companion to target screen coordinates."""
      self._fly_target = (x, y)
      # Offset so triangle tip points at the target
      target_x = x - int(self.WIDGET_W * 0.15)
      target_y = y - int(self.WIDGET_H * 0.15)

      self._pos_anim.stop()
      self._pos_anim.setStartValue(self.pos())
      self._pos_anim.setEndValue(QPoint(target_x, target_y))
      self._pos_anim.setDuration(400)
      self._pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
      self._pos_anim.start()
  ```

- [ ] **Step 3:** Add `return_to_cursor`:
  ```python
  def return_to_cursor(self) -> None:
      """Animate back to current cursor position, then resume tracking."""
      if self._fly_target is None:
          return
      self._fly_target = None

      cursor_pos = QCursor.pos()
      screen = QApplication.screenAt(cursor_pos)
      if screen is None:
          return
      geo = screen.geometry()
      screen_rect = (geo.x(), geo.y(), geo.width(), geo.height())
      placement = compute_position(
          cursor_pos.x(), cursor_pos.y(), screen_rect,
          companion_size=(self.WIDGET_W, self.WIDGET_H),
          offset=self.OFFSET, edge_margin=self.EDGE_MARGIN,
      )

      self._pos_anim.stop()
      self._pos_anim.setStartValue(self.pos())
      self._pos_anim.setEndValue(QPoint(placement.x, placement.y))
      self._pos_anim.setDuration(300)
      self._pos_anim.setEasingCurve(QEasingCurve.Type.InCubic)
      self._pos_anim.finished.connect(self._on_return_complete, Qt.ConnectionType.SingleShotConnection)
      self._pos_anim.start()

  def _on_return_complete(self) -> None:
      """Resume cursor tracking after return animation."""
      self._prev_x = 0
      self._prev_y = 0
      self._track_cursor(force=True)
  ```

- [ ] **Step 4:** Update `set_state` to trigger return on IDLE:
  In `set_state`, when entering IDLE, add:
  ```python
  if self._fly_target is not None:
      self.return_to_cursor()
  ```

- [ ] **Step 5:** Update `set_state` for LISTENING (interrupt handling):
  When entering LISTENING, add:
  ```python
  self._pos_anim.stop()
  self._fly_target = None
  ```
  This ensures a hotkey press during flight immediately stops the animation and resumes normal behavior.

- [ ] **Step 6:** Import `QPoint` from `PySide6.QtCore` if not already imported.

- [ ] **Step 7:** Test manually:
  - Open a visually distinctive app
  - Ask "where is [some button]?" → companion should fly to the element
  - Companion stays there during TTS
  - After TTS → companion returns to cursor
  - Interrupt test: press Ctrl+Alt mid-TTS while companion is pointed → returns immediately

- [ ] **Step 8:** Commit:
  ```
  feat(clicky-py): companion fly-to and return-to-cursor animation
  ```

---

## Execution rules (carried from v1/v2)

- Work directly on `main` branch
- Commit after every task — use exact commit messages above
- STOP at every slice boundary for manual verification before proceeding
- Surface unexpected failures — don't silently work around
- Execute via `superpowers:subagent-driven-development`, one task at a time

---

## Test summary at plan completion

| Test file | Module tested | Test count |
|-----------|--------------|------------|
| `test_point_mapper.py` | `map_point_to_screen` | 7 |
| (existing) `test_point_parser.py` | `parse_point_tag` | 9 |
| (existing v2 tests) | positioning, waveform bars, config, etc. | ~46 |
| **Total** | | **~62 tests** |
