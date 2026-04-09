# ClickyWin — Product Requirements Document

**Status:** Draft v1
**Date:** 2026-04-09
**Owner:** @JaySmith502
**Target release:** v1 (tray + push-to-talk + screenshot + Claude + TTS, no floating cursor)

---

## Problem Statement

I want to learn unfamiliar software (DaVinci Resolve, Blender, Photoshop, Unreal, any tool I've been procrastinating) **by doing, not by watching hour-long YouTube tutorials.** When I get stuck, I want a knowledgeable friend sitting next to me who can see what's on my screen, hear my question, and talk me through the next step in natural language.

That experience already exists on macOS — Farza's [Clicky](https://github.com/farzaa/clicky) and Jason Kneen's [CursorBuddy](https://github.com/jasonkneen/CursorBuddy) both deliver it via Swift menu-bar apps. **Neither runs on Windows.** I run Windows 11, and so do most of the people I'd want to demo this to or deploy it for (clients, presentation audiences, the broader Windows developer community).

The gap I'm solving: a Windows 10/11 native experience of "AI tutor that sees my screen and teaches me by voice" with the same conversational quality as Farza's mac version, released as an open-source community project that I can reference in talks and hand to clients.

---

## Solution

**ClickyWin** is a Windows 10/11 system tray app. Behavior from the user's perspective:

1. I launch ClickyWin. An icon appears in my system tray. On first run, a small panel pops up near the tray telling me to **"Hold Ctrl+Alt to talk to Clicky."**
2. I switch to DaVinci Resolve (or Blender, or whatever I'm learning). I hold **Ctrl+Alt** and say *"How do I add a LUT to this clip? I'm new to DaVinci."*
3. The ClickyWin panel auto-appears near my tray icon while I'm talking. I see a live waveform reacting to my voice and interim transcript text appearing as I speak.
4. I release Ctrl+Alt. The panel shows a processing spinner. In the background: my transcript plus a screenshot of every monitor I have gets sent to Claude (via my own Cloudflare Worker proxy, so my API keys never ship in the app).
5. Claude's response streams back into the panel as text — *"to add a LUT, right-click that node labeled zero-one in the node graph, and you'll see an option to apply a LUT"* — and simultaneously plays back through my speakers via ElevenLabs text-to-speech in a natural voice.
6. I can immediately follow up with another push-to-talk question — *"which LUT should I pick?"* — and Clicky remembers the DaVinci context from the previous turn.
7. If Claude is mid-response and I want to interrupt, I just press Ctrl+Alt again. Clicky cuts the audio, cancels the stream, and starts listening to my new question.
8. I can swap between Sonnet 4.6 (fast, cheap, default) and Opus 4.6 (slower, smarter) via a dropdown in the panel.
9. When I'm done, I click outside the panel and it hides. The tray icon stays. Clicky sleeps until I press the hotkey again.

The v1 target experience is **"Farza's Clicky minus the flying blue cursor"** — the floating cursor overlay and coordinate-pointing feature is the flashiest part of Farza's design but also the riskiest Windows engineering. Deferring it to v2 lets me ship a useful, resonant learner experience much sooner, then layer the cursor on top once the core loop is proven.

---

## User Stories

### First-run and setup

1. As a new user, I want to download a zip, unzip it, and double-click `ClickyWin.exe` to run, so that I don't need a complicated installer.
2. As a new user, I want the app to automatically create its config file on first launch, so that I don't need to hunt for example files.
3. As a new user, I want to see a clear first-run message telling me "Hold Ctrl+Alt to talk," so that I can immediately start using the app without reading docs.
4. As a new user, I want a clear error if my Cloudflare Worker URL is not configured, so that I know exactly what to fix before trying to talk to Clicky.
5. As a developer running from source, I want `uv sync && uv run python -m clicky` to just work, so that I can iterate without build steps.
6. As an OSS user, I want a one-paragraph README section on how to deploy my own Cloudflare Worker, so that I can get running in under 10 minutes.

### Push-to-talk interaction

7. As a user, I want to hold Ctrl+Alt anywhere in Windows (while focused on any app) and have ClickyWin capture my voice, so that I don't need to alt-tab to Clicky first.
8. As a user, I want to see a waveform reacting to my voice while I hold the hotkey, so that I know the mic is actually hearing me.
9. As a user, I want to see interim transcript text appear as I speak, so that I can tell Clicky is understanding me correctly before I finish my sentence.
10. As a user, I want Clicky to finalize my transcript the instant I release Ctrl+Alt, so that there's no perceivable delay between "I stopped talking" and "Clicky is thinking."
11. As a user, I want the panel to automatically appear near my tray when I press the hotkey (even if it was hidden), so that I always see visual feedback without manually clicking the tray.
12. As a user, I want to cancel a half-finished question by releasing Ctrl+Alt without speaking, so that an empty transcript doesn't trigger a pointless Claude call.
13. As a user holding Ctrl+Alt to talk, I want ClickyWin to NOT interfere with other Ctrl+Alt+X shortcuts, so that it doesn't break my existing muscle memory.
14. As a user on an international keyboard layout (where Ctrl+Alt = AltGr), I want to remap the hotkey via config file, so that I can still use Clicky without breaking my typing.

### Screen awareness

15. As a user, I want Clicky to see all my monitors when I ask a question, so that it can reference content on my secondary display if my question is about that screen.
16. As a user, I want Clicky to know which monitor my cursor is on when I press the hotkey, so that it prioritizes "the screen I'm actually looking at" as the primary focus.
17. As a user, I want screenshots compressed to a reasonable size before being sent, so that my upload bandwidth isn't hammered on every question.
18. As a user on a high-DPI display (125%, 150%, 200% scaling), I want screenshots to capture at physical pixel resolution, so that Clicky sees exactly what I see.
19. As a user, I don't want the ClickyWin panel to appear in the screenshot sent to Claude, so that Claude only sees my actual work.

### Claude conversation

20. As a user, I want Clicky to remember prior turns in our conversation, so that I can ask follow-ups like "which LUT should I pick?" without re-explaining that I'm in DaVinci.
21. As a user, I want the response to stream into the panel as Claude generates it, so that I can start reading before the full response arrives.
22. As a user, I want the response to be spoken aloud in a natural voice, so that I can listen while my hands stay on my software.
23. As a user, I want Clicky to sound like a friendly mentor, not a robot — short sentences, casual warmth, no dead-end "want me to explain more?" questions.
24. As a user, I want to switch between Sonnet 4.6 (faster, cheaper) and Opus 4.6 (smarter) via a dropdown in the panel, so that I can pick the right model for the complexity of my question.
25. As a user, I want to interrupt Clicky mid-sentence by pressing Ctrl+Alt again, so that I can redirect the conversation without waiting for it to finish.
26. As a user, I want conversation history capped at around 20 turns so my session doesn't balloon in cost and latency, with older turns automatically trimmed.
27. As a user, I want restarting the app to clear conversation history, so that I get a fresh start when I need one.

### Error handling

28. As a user, I want clear red error banners when the worker is unreachable or a key is missing, so that I immediately understand what's broken.
29. As a user, I want a helpful "Open Microphone Settings" button if mic access is blocked, so that I can fix it with one click.
30. As a user, I want error banners to auto-dismiss on the next successful turn, so that I don't have to manually clear them.
31. As a user, I want Clicky to fail loudly (not silently), so that I never wonder "did it hear me?"
32. As a user, I want errors logged to a rotating file at a well-known location, so that I can share a log when I need help debugging.

### Tray and panel UX

33. As a user, I want a color-coded tray icon (blue idle, green listening, amber responding), so that I can see Clicky's state at a glance without opening the panel.
34. As a user, I want clicking the tray icon to toggle the panel open/closed, so that I have manual control over visibility.
35. As a user, I want clicking outside the panel (or pressing Escape) to hide it, so that dismissing is intuitive.
36. As a user, I want the panel to stay open during a full conversation turn (listening → processing → responding → TTS), so that I always see what's happening.
37. As a user, I want the panel to be dark-themed and minimal, so that it visually matches Farza's original Clicky aesthetic.
38. As a user, I want a Quit button in the panel, so that I can cleanly exit without hunting through tray menus.

### OSS and community

39. As an OSS contributor, I want a clearly structured repo with Python source in one directory and the shared Cloudflare Worker in another, so that I can understand the architecture at a glance.
40. As an OSS contributor, I want a permissive license and prominent credit to Farza, so that the lineage is clear and I know what I can do with the code.
41. As a Windows developer learning from this code, I want well-organized modules that map one-to-one to concepts (hotkey, mic, screen capture, LLM, TTS, state machine), so that I can port or extract pieces for my own projects.
42. As a client demo audience member, I want to see a polished, working app I can believe in — not a scrappy prototype — so that the demo doesn't undermine the message.

---

## Implementation Decisions

### Platform and stack

- **Target:** Windows 10 22H2 minimum, Windows 11 primary. No Windows 7/8 legacy code paths.
- **Language:** Python 3.12 (sweet spot for PySide6 wheel availability and stability).
- **UI framework:** PySide6 (LGPL) with `QtWidgets` — not WinUI 3 (MSIX sandbox breaks low-level keyboard hooks), not Electron (`globalShortcut` swallows keys and can't distinguish modifier press/release), not Rust+Tauri (too much unfamiliar native surface for this user to iterate on).
- **Package manager:** `uv` (Astral), with `pyproject.toml` kept compatible with `pip install -e .` as a fallback for OSS users who prefer vanilla pip.
- **Binary distribution:** PyInstaller `--onedir` (folder bundle zipped for demo handoff), ~500ms cold start, no code signing in v1.

### Architecture

- **Deep modules with narrow interfaces** (per Ousterhout's *A Philosophy of Software Design*), wired together by an explicit orchestration layer:

  - **LLMClient** — sends streaming requests to the worker's `/chat` route, parses Anthropic SSE wire protocol including vision content blocks, emits token deltas via async callback. Named generically (`LLMClient`, not `ClaudeClient`) to make v2 OpenAI integration a drop-in subclass. **Gracefully ignores unknown SSE content-block types** so that future tool_use responses (MCP era) don't crash a v1 build.

  - **TranscriptionClient** — handles the full AssemblyAI v3 streaming lifecycle: fetch short-lived token from worker's `/transcribe-token`, open websocket to `streaming.assemblyai.com/v3/...`, frame PCM16 audio, track turn-based transcripts, emit interim + final events to the caller as an async iterator.

  - **TTSClient** — POSTs text to worker's `/tts` route, receives MP3 bytes, plays via `QMediaPlayer` backed by Windows Media Foundation (built into Windows, zero extra native deps). Emits `playback_finished` signal. Supports immediate stop for interrupt.

  - **ScreenCapture** — uses `mss` to grab all connected monitors, applies physical-pixel DPI awareness via `SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)` at startup, detects which monitor contains the mouse cursor, downscales to 1280 px long edge, encodes as JPEG quality 80, labels each image matching Farza's exact string format.

  - **MicCapture** — wraps `sounddevice` WASAPI capture at 16 kHz / 16-bit / mono / ~100 ms chunks. Emits two separate Qt signals: `pcm_chunk(bytes)` for downstream streaming, `audio_level(float)` for the waveform widget. Thread-safe emission from the audio callback.

  - **HotkeyMonitor** — wraps `pynput.keyboard.Listener` (listen-only low-level hook, never swallows keys). Enforces **strict modifier-only** semantics: start capture on "both Ctrl and Alt held and nothing else," cancel if any non-modifier key is pressed while held, finalize on release of either modifier. Configurable via config file for users with international keyboard conflicts.

  - **ConversationHistory** — pure in-memory list of `(user_transcript, assistant_text)` tuples, capped at 20 turns with FIFO eviction. Composes Claude request payloads: prior turns sent as text-only messages, current turn sent with both transcript and JPEG images attached. Not persisted to disk.

  - **Config** — loads TOML from `%APPDATA%\ClickyWin\config.toml` via the `platformdirs` library, auto-creates the file from a bundled example on first run, validates required fields (worker URL format, hotkey binding, model ID, log level), detects the unconfigured placeholder worker URL and flags it as invalid. Dev-mode override via env var.

- **Orchestration: CompanionManager** — owns the `VoiceState` enum (`idle` | `listening` | `processing` | `responding`), wires all deep modules together, handles interrupt (cancel in-flight LLM task + stop TTS + clear panel + start new capture), translates errors to red banner messages, emits signals that the UI layer binds to. Not a deep module — explicit orchestration, read top-to-bottom like a state machine.

- **Presentation layer:** `ClickyApp` (QApplication bootstrap, tray creation, lifecycle), `TrayIcon` (state-colored `QSystemTrayIcon`), `Panel` (frameless `QWidget` positioned near tray, hosts all sub-views), `WaveformView` (custom paint-event widget rendering an RMS bar history at 60 FPS), `TranscriptView` (interim + final transcript during listening), `ResponseView` (streaming Claude text during responding), `ModelPicker` (Sonnet/Opus dropdown), `PermissionsIndicator` (mic status pill), `StatusBanner` (error banners, auto-dismiss on next success).

### Worker proxy

- **Reuse Farza's existing `worker/src/index.ts` unchanged.** Three routes (`/chat`, `/tts`, `/transcribe-token`) already handle everything ClickyWin needs. Deploy to the user's own Cloudflare account as `clicky-win-proxy`. Python app's `config.toml` carries the deployed worker URL as its only required setting.
- API keys (`ANTHROPIC_API_KEY`, `ASSEMBLYAI_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`) live as Cloudflare secrets, never ship in the Python binary. This matches Farza's security model exactly.

### Claude request shape

- **Two models exposed to the user:** Sonnet 4.6 (default, fast/cheap) and Opus 4.6 (slower, deeper reasoning). Runtime-selectable via panel dropdown, default read from config.
- **Vision content:** each turn attaches one JPEG per monitor with a label string matching Farza's format (single screen: `"user's screen (cursor is here)"`; multi-screen: `"screen N of M — cursor is on this screen (primary focus)"` or `"screen N of M — secondary screen"`). Cursor-screen sorted first.
- **System prompt:** Farza's voice rules ported verbatim — one or two sentences by default, all lowercase, casual, write for the ear not the eye, no markdown/lists, no "want me to explain more?" dead-end questions, plant a seed at the end when it fits. Examples retargeted from Final Cut / Xcode to DaVinci Resolve / Blender / Photoshop / VS Code (Windows-app learner persona). **Element-pointing section removed entirely in v1** since the floating cursor is deferred to v2 — adding it back is a one-line change when v2 lands.
- **Max tokens:** 1024 per response (Farza's value).
- **Conversation history:** text-only prior turns, JPEGs only attached to the current turn.

### AssemblyAI wire protocol

- **v3 streaming endpoint** (`u3-rt-pro` model) via websocket. Worker provides a short-lived (480s) token through `/transcribe-token`. Python client opens a websocket with that token, streams PCM16 binary frames at ~100 ms chunks, receives turn-based JSON messages with interim and final transcripts. On key release, finalize the current turn and emit the final transcript. On websocket disconnect mid-stream, attempt one automatic reconnect before surfacing an error.

### Hotkey semantics

- **Default binding:** Ctrl+Alt held together (mirror of Farza's Ctrl+Option on macOS).
- **Detection:** modifier-only strict mode. Start capture when both Ctrl and Alt are held AND no non-modifier key is down. Cancel capture if any non-modifier key is pressed while both are held (preserves user's existing Ctrl+Alt+X shortcuts). Finalize on release of either modifier.
- **Configurable alternates:** `right_ctrl` option for users on international keyboard layouts where Ctrl+Alt conflicts with AltGr. A `caps_lock` binding was considered but deferred to v2 because it requires a suppressing keyboard hook to swallow the lock-toggle side effect, which contradicts the "never swallow keys" rule used for all other bindings.

### Panel behavior

- **Tray click:** toggles panel show/hide.
- **Hotkey press:** auto-shows panel near tray icon even if currently hidden.
- **During a conversation turn** (listening → processing → responding → TTS playing): panel stays open regardless of focus changes.
- **Dismissal:** click outside panel, or press Escape, or click the Quit button.
- **First-run:** if config file did not exist at startup, panel auto-opens with its normal state content (which includes the PTT instructions label). No separate onboarding modal.
- **Error state:** if config is invalid or worker URL is placeholder, panel auto-opens with a persistent colored banner until the user fixes and restarts.

### Logging and observability

- **Python `logging` module** configured with a `RotatingFileHandler` (max 5 MB, 3 backups) writing to `%APPDATA%\ClickyWin\logs\clicky.log`, plus a stderr handler for dev runs.
- **Log level** configurable via `config.toml` (`DEBUG` | `INFO` | `WARNING` | `ERROR`).
- **No analytics, no telemetry, no crash reporter** in v1.

### Build and distribution

- **Dev loop:** `uv sync`, then `uv run python -m clicky`. No compile step.
- **Demo build:** `uv run pyinstaller clicky.spec` produces a `dist/clicky/` folder. Zip and hand off.
- **Linter/formatter:** `ruff` (lint + format in one tool).
- **No type checker in v1** — `basedpyright` is a v2 add once the codebase stabilizes.

---

## Testing Decisions

### What makes a good test for this project

- **Test external behavior, not implementation.** A test should fail only if the observable output changes, not if an internal helper is renamed or a private field moves.
- **Pure functions first, wire-protocol parsers second, orchestration last.** The deepest modules with the narrowest interfaces give the highest test-value-to-effort ratio.
- **No live network calls.** Every HTTP / websocket test works off recorded fixture bytes. No AssemblyAI or Anthropic real-traffic tests — too expensive, too flaky, too slow.
- **No UI tests.** Async Qt widget tests are high-setup, low-signal for a tray app. Manual testing covers the UI.
- **No hardware tests.** Mic capture and screen capture depend on the host machine. Manual testing covers them.

### Modules with unit tests

1. **Config loader** — round-trip TOML parse, first-run file creation into a temp dir, validation failure modes (malformed TOML, missing required fields, placeholder worker URL detection), env-var override behavior.
2. **LLMClient SSE parser** — feed recorded Anthropic SSE fixtures byte-for-byte, assert that emitted text deltas assemble into the expected full response. Include a fixture with an unknown content-block type to verify defensive skipping.
3. **TranscriptionClient message parser** — feed recorded AssemblyAI v3 websocket JSON messages, assert correct turn-based interim vs final transcript extraction.
4. **ConversationHistory** — append behavior, 20-turn FIFO cap, composition of messages-for-request with text-only prior turns and images-only-on-current-turn semantics.
5. **ScreenCapture label composition** — pure function mapping `(cursor_monitor_index, total_monitors, current_index)` to the exact Farza label string. Isolate from the actual `mss` call.
6. **POINT tag parser** — even though v1 strips the element-pointing section from the prompt, a small parser for `[POINT:x,y:label:screenN]` is written in v1 in preparation for v2. Tested with positive fixtures, negative fixtures, and `[POINT:none]`.

### Modules without automated tests (manual verification)

- UI / `Panel` / `WaveformView` / `TrayIcon`
- `MicCapture` (hardware dependent)
- `ScreenCapture` actual mss invocation (desktop state dependent)
- `HotkeyMonitor` actual hook (needs a real keyboard)
- `CompanionManager` async orchestration (end-to-end feel, covered by "run the app and test each scenario manually")
- `TTSClient` playback (audio output dependent)

### Prior art

- Farza's Swift reference in `leanring-buddy/` defines the exact behaviors we are matching; its behavior is the de-facto test oracle. When we port a module, the Swift original is the reference for "is this right?"
- `CompanionScreenCaptureUtility.swift` in particular specifies exact screenshot dimensions (1280 long edge), JPEG quality (0.8), and label strings — ClickyWin's ScreenCapture test asserts those exact values.
- The system prompt in `CompanionManager.swift` defines the voice and example format; the Python port retargets examples from Mac apps to Windows apps but preserves the rules section verbatim.

### Test tooling

- `pytest` as runner
- `ruff` for lint and format, run in CI (when CI is added post-v1) and locally via `uv run ruff check .`
- Test count target for v1: **15–25 unit tests**, total suite runs in under 1 second

---

## Out of Scope

The following are explicitly deferred beyond v1. Each is called out so future-me (or a contributor) doesn't waste time trying to sneak them in early.

### Deferred to v2

1. **Floating cursor overlay** — the blue cursor that flies to and points at UI elements via `[POINT:x,y:label:screenN]` tags. This is the flashiest part of Farza's Clicky and the hardest Windows engineering (transparent click-through layered top-most window, per-monitor DPI coordinate mapping, bezier-arc animations). Deferred intentionally so v1 can prove the core loop.
2. **Element-pointing system prompt section** — removed in v1 to save tokens and because there's nothing to render. Added back in v2 when the overlay lands.
3. **"Show Clicky" persistent cursor mode** — Farza's toggle where the cursor is always visible following the mouse. Depends on v2 overlay.
4. **Transient cursor fade behavior** — fades cursor in during interaction, out on idle. Depends on v2 overlay.

### Deferred to v2 or later

5. **OpenAI provider support** — the `LLMClient` interface is designed to accommodate it (generic name, subclass-friendly), but the v1 build is Claude-only. v2 adds a `/chat-openai` Worker route, an `OpenAIClient` subclass, and a second tuned system prompt.
6. **MCP (Model Context Protocol) integration** — inspired by CursorBuddy's recent addition. v2+ could let Claude execute tools on the Windows machine (shell commands, file I/O, open URLs, clipboard) via the official Python `mcp` SDK. Genuinely differentiating for a "tutor that can actually fix things" experience.
7. **Built-in tool set** — Windows equivalents of CursorBuddy's `execute_command`, `read_file`, `write_file`, `list_directory`, `search_files`, `open_url`, `open_application`, `get_clipboard`, `set_clipboard`. All trivial in Python. Pairs with #6.
8. **Alternate TTS providers** — Cartesia (lower latency than ElevenLabs), OpenAI TTS (cheaper). Same HTTP-POST-then-play pattern.
9. **Alternate STT providers** — Deepgram (fast streaming), OpenAI Whisper API (upload-based fallback), local `faster-whisper` or `vosk` models for offline use.
10. **Streaming ElevenLabs TTS** — reduce time-to-first-audio by starting playback before the full MP3 is received.
11. **Auto-update** — a Sparkle-equivalent for Python. Likely a hand-rolled "version check on startup → notification banner → user downloads new zip" flow, ~30 lines.
12. **Analytics** — opt-in PostHog or similar, only once there are real users and a real reason to learn from usage.
13. **Code signing** — standard or EV certificate to eliminate Windows SmartScreen "Unknown publisher" dialog. Worth buying when handing ClickyWin to clients as a turnkey install.
14. **Proper `.ico` artwork** — v1 uses a programmatic Pillow-drawn placeholder; public release gets a commissioned or AI-generated icon.
15. **MSI / MSIX installer** — plain zipped folder is sufficient for v1. Installer comes with the polished public release.
16. **Type checking** — `basedpyright` added once the codebase is stable enough that annotations pay off.
17. **UI tests** — `pytest-qt` or similar, if the UI grows complex enough to warrant it.
18. **Conversation history persistence** — currently in-memory only. Could persist to SQLite per session if users start asking for it.
19. **Settings pane with keybind picker UI** — currently config-file-only for hotkey binding. A proper settings window with a "press the key combo you want" capture widget is a nice polish.
20. **Multi-language support** — v1 uses whatever AssemblyAI / Claude default to; explicit language selection comes later if needed.

### Never in scope

- Windows 7 / 8 / 8.1 support
- Linux or Mac builds (Farza already has mac; Linux is a different community project)
- Direct API key embedding in the client (security regression from the Worker proxy)
- MSIX Store distribution (sandbox breaks LL keyboard hook)

---

## Further Notes

### Repo layout

Development happens in a sibling `clicky-py/` directory inside this workspace alongside Farza's read-only `leanring-buddy/` Swift reference and the shared `worker/` Cloudflare code. The upstream git relationship with `farzaa/clicky` is preserved in this fork — no renames, no disruptive reorganization of existing directories.

When v1 is demo-ready, a separate public GitHub repo named `clickywin` will be cut containing only `clicky-py/`, `worker/`, a fresh README crediting Farza prominently, and a LICENSE preserving Farza's MIT copyright alongside a new copyright line for the Python port.

### Naming conventions

- **User-facing brand:** "ClickyWin" everywhere a user sees it (tray tooltip, window title, panel header, README).
- **Public GitHub repo:** `clickywin` (lowercase smash, GitHub convention).
- **Built executable:** `ClickyWin.exe` (Windows CamelCase convention).
- **Local dev directory:** `clicky-py/` (internal, kept short).
- **Python package (import name):** `clicky` (internal, never user-facing, shorter import reads better than `import clickywin`).

### Market validation

While scoping this project we discovered [`jasonkneen/CursorBuddy`](https://github.com/jasonkneen/CursorBuddy) (formerly "Pucks"), a second active project in the voice + screen + AI tutor space. It's macOS-only (Xcode 26 / Swift 6.2 / macOS 26 SDK), so it doesn't solve the Windows gap, but it validates that this product category is real and has multiple independent builders. Key ideas from CursorBuddy worth borrowing for v2+: MCP integration, built-in tools, Cartesia TTS, Deepgram STT. Key design decisions we are NOT copying: storing API keys in a local JSON file instead of a Worker proxy (worse security for OSS distribution) and Liquid Glass lens (macOS 26 exclusive).

### Positioning

When this ships as OSS, the public README should lead with:

> **ClickyWin** — a Windows port of [Clicky by Farza](https://github.com/farzaa/clicky). The Mac community has Clicky and [CursorBuddy](https://github.com/jasonkneen/CursorBuddy); this is the Windows answer. Built in Python + PySide6 so Windows developers can read, fork, and extend every line.

### Known open items to verify during implementation

- Exact chunk size Farza uses for AssemblyAI streaming (likely 100 ms / 1600 samples at 16 kHz, but `BuddyAudioConversionSupport.swift` should be checked before locking).
- Exact conversation history cap in Farza's mac code (we are assuming ~20 turns; confirm during port).
- Farza's exact `GlobalPushToTalkShortcutMonitor.swift` press/release semantics (we are assuming strict modifier-only with cancel-on-chord; confirm during port).
- AssemblyAI v3 wire protocol version that Farza's Swift code targets — verify the endpoint URL, token query parameters, and JSON message shape match what the Python `websockets` client will send.

### Reference artifacts in this workspace

- `leanring-buddy/` — Farza's Swift source, read-only during the port.
- `worker/src/index.ts` — shared Cloudflare Worker, unchanged.
- `AGENTS.md` — Farza's AI-agent instructions for the mac repo (architecture summary, key files table, conventions).
- `Clicky_intro_video.txt` — transcript of Farza's X demo video where he uses Clicky to learn DaVinci Resolve. Defines the target user and the target experience.
- `docs/PRD.md` — this document.
