# ClickyWin v2.1 — Cursor Guidance

**Status:** Draft v2.1
**Date:** 2026-04-12
**Owner:** @JaySmith502
**Target release:** v2.1 (cursor guidance via POINT tags)
**Depends on:** v2 (clickywin-v2.0.0) — companion widget, point_parser, screen capture

---

## Problem Statement

ClickyWin v2 can see the user's screen and answer questions about it via voice, but when Claude says "click the color inspector button in the top right," the user has to visually scan the screen to find it. The companion triangle just stays frozen near the cursor during TTS — it doesn't guide the user's eyes to what Claude is referencing. This defeats the purpose of a screen-aware tutor. The user should be able to glance at where the companion is pointing and immediately see the relevant UI element.

---

## Solution

When Claude's response references a specific UI element on screen, it appends a `[POINT:x,y:label]` tag at the end of the response. The companion triangle flies from its current position to those coordinates on the actual screen, stays there during TTS playback so the user can see exactly what Claude is talking about, and returns to following the cursor when the turn ends. The POINT tag is stripped from the text before TTS so it's never spoken aloud.

This is the same behavior Farza's original Clicky implements on macOS — a blue cursor that independently flies to UI elements it's describing. The POINT tag parser already exists in ClickyWin (built in v1 Task 7.1), and the system prompt update follows Farza's battle-tested wording.

---

## User Stories

1. As a Windows learner, I want the companion to fly to the button Claude is describing so I can immediately see what it's referencing without scanning the screen.
2. As a Windows learner, I want the companion to stay at the pointed element while Claude speaks so I have time to look at it and understand.
3. As a Windows learner, I want the companion to return to following my cursor after the response ends so it doesn't get stuck somewhere.
4. As a Windows learner, I want the fly-to animation to be smooth and fast so it feels like the companion is guiding me, not lagging.
5. As a Windows learner using multiple monitors, I want the companion to fly to elements on any screen, not just the one my cursor is on.
6. As a Windows learner, I want Claude to point at things proactively when it would help, without me having to ask.
7. As a Windows learner, I want Claude to NOT point at things when it would be pointless, like during a general knowledge question.
8. As a Windows learner, I want the POINT tag to never be spoken aloud during TTS — only the natural response should be voiced.
9. As a Windows learner, I want the companion to show the correct position even when my screenshot was downscaled, mapping coordinates back to real screen pixels.
10. As a Windows learner, I want the companion's pointing to be approximate but useful — "in this area" guidance is sufficient, pixel-perfect accuracy is not required.
11. As a Windows learner, I want to interrupt a pointed response with a new push-to-talk, and have the companion immediately return to cursor-following for the new question.
12. As a developer, I want the coordinate mapping logic to be pure math I can unit test independently.
13. As a developer, I want the screen capture metadata (scale factors, monitor offsets) to be part of the capture output so coordinate mapping doesn't require recalculation.
14. As a developer, I want the POINT parsing to happen after the full response is assembled, not during streaming deltas, since the tag is always at the end.

---

## Implementation Decisions

### System Prompt Update

Append Farza's element-pointing section to the existing companion voice system prompt. The section instructs Claude to append `[POINT:x,y:label]` when pointing would help, `[POINT:none]` when it wouldn't, and provides examples of both. Coordinates are in screenshot image space (the downscaled JPEG dimensions), not raw screen pixels. The prompt tells Claude to use the dimension labels on the screenshot images.

### Screenshot Metadata Enrichment

The ScreenshotImage dataclass gains three new fields: `scale` (the downscale ratio applied, e.g. 0.667 for 1920→1280), `monitor_left` and `monitor_top` (the global pixel origin of that monitor). These are populated during capture since the values are already computed in the capture loop. No new computation needed — just surfacing existing data.

### Coordinate Mapping

A new pure function maps POINT tag coordinates from screenshot image space to real screen coordinates:
- `real_x = monitor_left + int(point_x / scale)`
- `real_y = monitor_top + int(point_y / scale)`

Screen selection: no `:screenN` in the tag → use the first screenshot (cursor's screen). `:screen2` → use the second screenshot's metadata. Out-of-range screen numbers fall back to cursor's screen.

### Response Pipeline Integration

After `response_complete` fires in CompanionManager:
1. Parse POINT tag from full response text via existing `parse_point_tag()`
2. If a PointTag is returned, map coordinates to screen pixels via the new mapper using stored screenshot metadata from the current turn
3. Tell companion widget to `fly_to(real_x, real_y)`
4. Send `spoken_text` (tag stripped) to TTS — not the raw response

The CompanionManager must retain the screenshot metadata from the current turn's capture so it's available when the response completes.

### Companion Widget Animation

Two new methods on CompanionWidget:
- `fly_to(x, y)` — animate from current widget position to (x, y) using QPropertyAnimation on the `pos` property, 400ms duration, OutCubic easing. Pauses cursor tracking during flight.
- `return_to_cursor()` — animate from current position to `QCursor.pos()`, 300ms InCubic easing. On animation complete, resume cursor tracking.

`fly_to` is called by CompanionManager when a POINT tag is found. `return_to_cursor` is triggered on the transition to IDLE state (which already unfreezes cursor tracking).

### POINT:none Handling

When the parser returns None (either `[POINT:none]` or no tag at all), no fly-to occurs. The companion stays frozen at its current position during TTS as it already does. The spoken text is still stripped of the tag before TTS.

### Interrupt Handling

If the user presses Ctrl+Alt during a pointed response (interrupt), the state transitions to LISTENING. Any in-flight `fly_to` animation is stopped, `return_to_cursor()` is called immediately, and normal cursor tracking resumes. This uses the existing interrupt path in CompanionManager — the only addition is stopping the position animation.

---

## Testing Decisions

Good tests for this feature test pure coordinate math through public interfaces, not animation behavior or Qt rendering.

### Modules to Test

**1. Point coordinate mapper** (`test_point_mapper.py`)
- Given a PointTag with (640, 360) and a screenshot with scale=0.667, monitor at (0,0) → real coords (960, 540)
- Given a PointTag with screen=2 and two screenshots → uses second screenshot's monitor offset
- Given a PointTag with screen=3 but only 2 screenshots → falls back to first screenshot
- Given a PointTag with no screen specified → uses first screenshot (cursor screen)
- Given scale=1.0 (no downscale, small monitor) → coords pass through unchanged plus monitor offset
- Multi-monitor offset: PointTag (100, 100) on screen2 at monitor offset (1920, 0) with scale=0.5 → real (2120, 200)

**2. Existing point_parser tests** — already cover all tag formats (9 tests, passing)

**Prior art:** `test_companion_position.py`, `test_waveform_bars.py` — same pattern of testing pure math functions.

### Modules NOT Tested

- System prompt text changes — content, not logic
- CompanionManager pipeline integration — orchestration, tested via manual smoke test
- QPropertyAnimation fly-to/return — visual, not CI-testable

---

## Out of Scope

- **Visual indicator at the pointed element** — no highlight ring, label overlay, or arrow drawn at the target. The companion triangle itself IS the pointer.
- **Animated cursor trail** — no path visualization between origin and destination.
- **POINT tag during streaming** — tags are only parsed from the complete response, not mid-stream. Streaming POINT would require speculative parsing and partial animations.
- **POINT accuracy improvement** — if Claude's coordinate estimation is off, that's a model-level issue. No client-side correction, snapping, or accessibility-tree lookup.
- **Configurable animation speed** — hardcoded 400ms/300ms. Tuneable in v3 if needed.
- **Element label display** — the PointTag includes a `label` field but we don't render it on screen. Could show as a tooltip in v3.

---

## Further Notes

- The POINT tag parser was built in v1 Task 7.1 specifically as "v2 overlay prep." This feature is its intended consumer.
- Farza's prompt wording is battle-tested across thousands of Clicky users. Reusing it verbatim avoids prompt engineering risk.
- Coordinate accuracy will be approximate (within ~50-100px). This is acceptable — the companion guides the user's eyes to "this area of the screen," not to an exact pixel. Users can find the exact button once they're looking in the right region.
- The screenshot metadata enrichment (scale, monitor offsets) is also useful for future features like drawing highlight rectangles or element bounding boxes.
- If the companion flies to a position near a screen edge, the existing edge-flip logic in `compute_position` doesn't apply — `fly_to` sets an absolute position. This is correct because we want the companion AT the element, not offset from it.
