# ClickyWin v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Spec:** `docs/PRD.md` — read it before starting any task. The PRD is the source of truth for all behavior; this plan is the sequencing and verification layer.
>
> **Reference implementation:** `leanring-buddy/` (Farza's Swift source, read-only). Every Python module has a Swift analog to cross-check behavior.

**Goal:** Ship a Windows 10/11 tray app that lets you push-to-talk to Claude while it sees your screen, streams a spoken response back, and remembers prior turns — the voice + screen + teach-me-by-doing experience of Farza's macOS Clicky, ported to Python + PySide6, minus the floating cursor overlay (deferred to v2).

**Architecture:** Deep modules (`Config`, `LLMClient`, `TranscriptionClient`, `TTSClient`, `ScreenCapture`, `MicCapture`, `HotkeyMonitor`, `ConversationHistory`) with narrow interfaces, wired together by an explicit orchestration layer (`CompanionManager`). A PySide6 `QApplication` hosts a tray icon and a frameless panel that auto-opens on hotkey press and shows live waveform → interim transcript → streaming response. All API keys live behind a Cloudflare Worker proxy (unchanged from Farza's repo).

**Tech Stack:** Python 3.12, PySide6 (LGPL), `uv` package manager, `sounddevice` (WASAPI mic), `mss` (multi-monitor screen capture), `pynput` (low-level keyboard hook), `httpx` (HTTP + SSE), `websockets` (AssemblyAI v3 streaming), `Pillow` (image encoding + icon), `platformdirs` (config path resolution), `tomllib` (stdlib TOML reader), `pytest` + `ruff` for tests + lint.

**Execution notes:**
- Work happens in a new directory `clicky-py/` inside this workspace, alongside `leanring-buddy/` and `worker/`.
- Use @superpowers:test-driven-development for every task marked `[TDD]`. For UI / hardware / network-integration tasks (marked `[IMPL]`), write a minimal implementation, then manually verify per the listed acceptance criteria, then commit.
- Commit after every task. Messages in imperative mood, one-line explaining the "why".
- When a task says "verify against Swift", open the listed Swift file and confirm behavior matches before declaring done.

---

## File Structure

### New directory (all tasks create files here)

```
clicky-py/
├── pyproject.toml                    # uv-managed deps, Python 3.12 target
├── uv.lock                           # generated, committed
├── README.md                         # dev instructions, created late
├── config.example.toml               # shipped example config
├── clicky.spec                       # PyInstaller spec (Phase 7)
├── clicky/
│   ├── __init__.py
│   ├── __main__.py                   # `python -m clicky` entry point
│   ├── app.py                        # ClickyApp: QApplication bootstrap
│   ├── config.py                     # Config dataclass + loader [TDD]
│   ├── logging_config.py             # RotatingFileHandler + stderr
│   ├── design_system.py              # Ported DesignSystem.swift tokens
│   ├── state.py                      # VoiceState enum
│   ├── companion_manager.py          # Orchestration state machine
│   ├── hotkey.py                     # HotkeyMonitor (pynput)
│   ├── mic_capture.py                # MicCapture (sounddevice)
│   ├── screen_capture.py             # ScreenCapture (mss) [TDD label composer]
│   ├── conversation_history.py       # ConversationHistory [TDD]
│   ├── prompts.py                    # System prompt constants
│   ├── point_parser.py               # [POINT:x,y:label:screenN] parser [TDD, v2 prep]
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── llm_client.py             # LLMClient base + ClaudeClient subclass [TDD SSE parser]
│   │   ├── transcription_client.py   # TranscriptionClient (AssemblyAI v3) [TDD message parser]
│   │   └── tts_client.py             # TTSClient (ElevenLabs + QMediaPlayer)
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── tray_icon.py              # State-colored QSystemTrayIcon
│   │   ├── panel.py                  # Frameless panel host
│   │   ├── waveform_view.py          # Custom paintEvent widget
│   │   ├── transcript_view.py        # Interim + final transcript display
│   │   ├── response_view.py          # Streaming Claude response
│   │   ├── model_picker.py           # Sonnet/Opus dropdown
│   │   ├── status_banner.py          # Error / warning banner
│   │   └── permissions_indicator.py  # Mic permission pill
│   └── icon_factory.py               # Programmatic Pillow icon generator
└── tests/
    ├── __init__.py
    ├── conftest.py                   # pytest fixtures
    ├── test_config.py
    ├── test_conversation_history.py
    ├── test_llm_sse_parser.py
    ├── test_transcription_parser.py
    ├── test_screen_capture_labels.py
    ├── test_point_parser.py
    └── fixtures/
        ├── anthropic_sse_basic.txt       # recorded SSE bytes
        ├── anthropic_sse_unknown_block.txt  # defensive parsing fixture
        └── assemblyai_v3_messages.json   # recorded websocket JSON
```

### Existing files (referenced only, NOT modified)

- `leanring-buddy/CompanionManager.swift` — reference for state machine, system prompt, parsePointingCoordinates
- `leanring-buddy/ClaudeAPI.swift` — reference for Anthropic SSE wire protocol
- `leanring-buddy/AssemblyAIStreamingTranscriptionProvider.swift` — reference for v3 websocket protocol
- `leanring-buddy/CompanionScreenCaptureUtility.swift` — reference for label format and downscaling config
- `leanring-buddy/ElevenLabsTTSClient.swift` — reference for TTS request shape
- `leanring-buddy/BuddyDictationManager.swift` — reference for mic capture + PCM conversion
- `leanring-buddy/BuddyAudioConversionSupport.swift` — reference for PCM16 chunk size
- `leanring-buddy/GlobalPushToTalkShortcutMonitor.swift` — reference for hotkey press/release semantics
- `leanring-buddy/DesignSystem.swift` — reference for color tokens and corner radii
- `leanring-buddy/MenuBarPanelManager.swift` — reference for panel positioning near tray
- `worker/src/index.ts` — deployed unchanged to user's Cloudflare account

---

## Phase 1: Foundation (scaffold, config, tray, panel shell, hotkey)

**Milestone:** App launches from `uv run python -m clicky`, tray icon appears, clicking the tray toggles a frameless dark panel, pressing Ctrl+Alt prints press/release to stderr. Config loads from `%APPDATA%\ClickyWin\config.toml` and auto-creates on first run.

---

### Task 1.1: Scaffold `clicky-py/` with `pyproject.toml` and dependency install [IMPL]

**Files:**
- Create: `clicky-py/pyproject.toml`
- Create: `clicky-py/clicky/__init__.py` (empty)
- Create: `clicky-py/clicky/__main__.py` (placeholder `print("clicky")`)
- Create: `clicky-py/tests/__init__.py` (empty)

**Steps:**

- [ ] **Step 1:** Create `clicky-py/pyproject.toml` with:
  ```toml
  [project]
  name = "clicky"
  version = "0.1.0"
  description = "ClickyWin — voice tutor for Windows learners. Python port of Farza's Clicky."
  requires-python = ">=3.12,<3.13"
  dependencies = [
      "pyside6>=6.7",
      "sounddevice>=0.4.6",
      "mss>=9.0",
      "pynput>=1.7.6",
      "httpx>=0.27",
      "websockets>=12.0",
      "pillow>=10.0",
      "platformdirs>=4.0",
  ]

  [dependency-groups]
  dev = [
      "pytest>=8.0",
      "ruff>=0.5",
      "pyinstaller>=6.0",
  ]

  [project.scripts]
  clicky = "clicky.__main__:main"

  [tool.ruff]
  line-length = 100
  target-version = "py312"

  [tool.ruff.lint]
  select = ["E", "F", "W", "I", "UP", "B", "SIM"]

  [build-system]
  requires = ["hatchling"]
  build-backend = "hatchling.build"

  [tool.hatch.build.targets.wheel]
  packages = ["clicky"]
  ```

- [ ] **Step 2:** Create minimal `clicky-py/clicky/__init__.py` and `clicky-py/clicky/__main__.py`:
  ```python
  # __main__.py
  def main() -> None:
      print("clicky")


  if __name__ == "__main__":
      main()
  ```

- [ ] **Step 3:** Create empty `clicky-py/tests/__init__.py`.

- [ ] **Step 4:** From `clicky-py/`, run `uv sync` and verify all dependencies install without error. Note any wheels that need a native build (none expected).

- [ ] **Step 5:** Run `uv run python -m clicky` from inside `clicky-py/`. Expected: prints `clicky` and exits 0.

- [ ] **Step 6:** Run `uv run ruff check .` from inside `clicky-py/`. Expected: no warnings on the scaffold.

- [ ] **Step 7:** Commit:
  ```bash
  git add clicky-py/pyproject.toml clicky-py/uv.lock clicky-py/clicky clicky-py/tests
  git commit -m "feat(clicky-py): scaffold python package and dependencies"
  ```

---

### Task 1.2: `Config` dataclass with TOML loader and validation [TDD]

**Files:**
- Create: `clicky-py/clicky/config.py`
- Create: `clicky-py/tests/test_config.py`
- Create: `clicky-py/config.example.toml`

Reference: PRD § Implementation Decisions → Config. The config file shape is defined in PRD § further notes and Question 11c.

**Steps:**

- [ ] **Step 1:** Write failing tests in `clicky-py/tests/test_config.py`:
  ```python
  from pathlib import Path

  import pytest

  from clicky.config import Config, ConfigError, PLACEHOLDER_WORKER_URL


  def test_load_valid_config(tmp_path: Path) -> None:
      toml_text = """
      worker_url = "https://my-worker.example.workers.dev"
      hotkey = "ctrl+alt"
      default_model = "claude-sonnet-4-6"
      log_level = "INFO"
      """
      config_path = tmp_path / "config.toml"
      config_path.write_text(toml_text)
      cfg = Config.from_path(config_path)
      assert cfg.worker_url == "https://my-worker.example.workers.dev"
      assert cfg.hotkey == "ctrl+alt"
      assert cfg.default_model == "claude-sonnet-4-6"
      assert cfg.log_level == "INFO"


  def test_load_rejects_placeholder_worker_url(tmp_path: Path) -> None:
      toml_text = f"""
      worker_url = "{PLACEHOLDER_WORKER_URL}"
      hotkey = "ctrl+alt"
      default_model = "claude-sonnet-4-6"
      log_level = "INFO"
      """
      config_path = tmp_path / "config.toml"
      config_path.write_text(toml_text)
      with pytest.raises(ConfigError, match="worker_url"):
          Config.from_path(config_path)


  def test_load_rejects_invalid_toml(tmp_path: Path) -> None:
      config_path = tmp_path / "config.toml"
      config_path.write_text("this is not valid toml {{{")
      with pytest.raises(ConfigError, match="parse"):
          Config.from_path(config_path)


  def test_load_rejects_missing_required_field(tmp_path: Path) -> None:
      config_path = tmp_path / "config.toml"
      config_path.write_text('hotkey = "ctrl+alt"\n')  # missing worker_url
      with pytest.raises(ConfigError, match="worker_url"):
          Config.from_path(config_path)


  def test_load_rejects_invalid_hotkey(tmp_path: Path) -> None:
      toml_text = """
      worker_url = "https://my-worker.example.workers.dev"
      hotkey = "banana"
      default_model = "claude-sonnet-4-6"
      log_level = "INFO"
      """
      config_path = tmp_path / "config.toml"
      config_path.write_text(toml_text)
      with pytest.raises(ConfigError, match="hotkey"):
          Config.from_path(config_path)


  def test_load_rejects_invalid_model(tmp_path: Path) -> None:
      toml_text = """
      worker_url = "https://my-worker.example.workers.dev"
      hotkey = "ctrl+alt"
      default_model = "gpt-4"
      log_level = "INFO"
      """
      config_path = tmp_path / "config.toml"
      config_path.write_text(toml_text)
      with pytest.raises(ConfigError, match="default_model"):
          Config.from_path(config_path)


  def test_ensure_exists_creates_from_example(tmp_path: Path) -> None:
      example_path = tmp_path / "config.example.toml"
      example_path.write_text('worker_url = "placeholder"\n')
      target_path = tmp_path / "nested" / "config.toml"
      Config.ensure_exists(target_path, example_path)
      assert target_path.exists()
      assert target_path.read_text() == example_path.read_text()


  def test_ensure_exists_noop_when_already_present(tmp_path: Path) -> None:
      example_path = tmp_path / "config.example.toml"
      example_path.write_text('worker_url = "placeholder"\n')
      target_path = tmp_path / "config.toml"
      target_path.write_text('worker_url = "real"\n')
      Config.ensure_exists(target_path, example_path)
      assert target_path.read_text() == 'worker_url = "real"\n'
  ```

- [ ] **Step 2:** Run `uv run pytest tests/test_config.py -v` from inside `clicky-py/`. Expected: all tests fail with `ModuleNotFoundError: clicky.config`.

- [ ] **Step 3:** Implement `clicky-py/clicky/config.py`:
  ```python
  """Config loader for ClickyWin.

  Reads config.toml from the OS-appropriate per-user config directory via
  platformdirs. Validates required fields and detects the unconfigured placeholder
  worker URL (so the panel can surface a clear first-run warning).
  """

  from __future__ import annotations

  import shutil
  import tomllib
  from dataclasses import dataclass
  from pathlib import Path

  PLACEHOLDER_WORKER_URL = "https://clicky-win-proxy.your-subdomain.workers.dev"

  # v1 supports the two listen-only-hook-friendly bindings. caps_lock is
  # deferred to v2 because it requires a suppressing hook to swallow the
  # lock-toggle side effect, which contradicts our "never swallow keys" rule.
  ALLOWED_HOTKEYS = {"ctrl+alt", "right_ctrl"}
  ALLOWED_MODELS = {"claude-sonnet-4-6", "claude-opus-4-6"}
  ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


  class ConfigError(Exception):
      """Raised when the config file cannot be loaded or fails validation."""


  @dataclass(frozen=True)
  class Config:
      worker_url: str
      hotkey: str
      default_model: str
      log_level: str

      @classmethod
      def from_path(cls, path: Path) -> Config:
          try:
              raw = path.read_bytes()
          except OSError as exc:
              raise ConfigError(f"cannot read config file at {path}: {exc}") from exc
          try:
              data = tomllib.loads(raw.decode("utf-8"))
          except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
              raise ConfigError(f"cannot parse TOML at {path}: {exc}") from exc

          worker_url = data.get("worker_url")
          if not isinstance(worker_url, str) or not worker_url:
              raise ConfigError("worker_url is required and must be a non-empty string")
          if worker_url == PLACEHOLDER_WORKER_URL:
              raise ConfigError(
                  f"worker_url is still the placeholder value. Edit {path} and set it to "
                  "your deployed Cloudflare Worker URL."
              )

          hotkey = data.get("hotkey", "ctrl+alt")
          if hotkey not in ALLOWED_HOTKEYS:
              raise ConfigError(
                  f"hotkey must be one of {sorted(ALLOWED_HOTKEYS)}, got {hotkey!r}"
              )

          default_model = data.get("default_model", "claude-sonnet-4-6")
          if default_model not in ALLOWED_MODELS:
              raise ConfigError(
                  f"default_model must be one of {sorted(ALLOWED_MODELS)}, got {default_model!r}"
              )

          log_level = data.get("log_level", "INFO")
          if log_level not in ALLOWED_LOG_LEVELS:
              raise ConfigError(
                  f"log_level must be one of {sorted(ALLOWED_LOG_LEVELS)}, got {log_level!r}"
              )

          return cls(
              worker_url=worker_url,
              hotkey=hotkey,
              default_model=default_model,
              log_level=log_level,
          )

      @staticmethod
      def ensure_exists(target_path: Path, example_path: Path) -> bool:
          """Copy example to target if target does not exist. Returns True if created."""
          if target_path.exists():
              return False
          target_path.parent.mkdir(parents=True, exist_ok=True)
          shutil.copyfile(example_path, target_path)
          return True
  ```

- [ ] **Step 4:** Create `clicky-py/config.example.toml` with the exact content specified in the PRD's "Proposed `config.example.toml`" section (Question 11c).

- [ ] **Step 5:** Run `uv run pytest tests/test_config.py -v`. Expected: all tests pass.

- [ ] **Step 6:** Commit:
  ```bash
  git add clicky-py/clicky/config.py clicky-py/tests/test_config.py clicky-py/config.example.toml
  git commit -m "feat(clicky-py): add config loader with TOML validation"
  ```

---

### Task 1.3: `ClickyApp` bootstrap with `QApplication` and config resolution [IMPL]

**Files:**
- Create: `clicky-py/clicky/app.py`
- Modify: `clicky-py/clicky/__main__.py`

Reference: PRD § Implementation Decisions → Presentation layer.

**Steps:**

- [ ] **Step 1:** Create `clicky-py/clicky/app.py`:
  ```python
  """ClickyWin QApplication bootstrap.

  Resolves the config file path via platformdirs, ensures the file exists
  (creating from config.example.toml on first run), loads it, and holds
  the resulting Config for downstream components to read.
  """

  from __future__ import annotations

  import sys
  from dataclasses import dataclass
  from pathlib import Path

  from PySide6.QtWidgets import QApplication
  from platformdirs import user_config_dir, user_log_dir

  from clicky.config import Config, ConfigError

  APP_NAME = "ClickyWin"
  APP_AUTHOR = "ClickyWin"


  @dataclass
  class BootstrapResult:
      app: QApplication
      config: Config | None
      config_error: ConfigError | None
      was_first_run: bool
      config_path: Path
      log_dir: Path


  def _example_config_path() -> Path:
      # config.example.toml sits next to the clicky package directory.
      return Path(__file__).resolve().parent.parent.parent / "config.example.toml"


  def bootstrap(argv: list[str] | None = None) -> BootstrapResult:
      argv = argv if argv is not None else sys.argv
      app = QApplication(argv)
      app.setApplicationName(APP_NAME)
      app.setOrganizationName(APP_AUTHOR)
      app.setQuitOnLastWindowClosed(False)  # tray app — closing panel must not quit

      # Pass appauthor=False so platformdirs does NOT nest a redundant
      # second "ClickyWin" folder inside the first (which happens when
      # appname == appauthor on Windows). We want %APPDATA%\ClickyWin\config.toml,
      # not %APPDATA%\ClickyWin\ClickyWin\config.toml.
      config_dir = Path(user_config_dir(APP_NAME, appauthor=False, roaming=True))
      config_path = config_dir / "config.toml"
      log_dir = Path(user_log_dir(APP_NAME, appauthor=False))

      was_first_run = Config.ensure_exists(config_path, _example_config_path())

      try:
          config = Config.from_path(config_path)
          config_error = None
      except ConfigError as exc:
          config = None
          config_error = exc

      return BootstrapResult(
          app=app,
          config=config,
          config_error=config_error,
          was_first_run=was_first_run,
          config_path=config_path,
          log_dir=log_dir,
      )
  ```

- [ ] **Step 2:** Update `clicky-py/clicky/__main__.py`:
  ```python
  """ClickyWin entry point: `python -m clicky`."""

  from __future__ import annotations

  import sys

  from clicky.app import bootstrap


  def main() -> int:
      result = bootstrap()
      if result.was_first_run:
          print(f"[clicky] first run: created config at {result.config_path}")
      if result.config_error is not None:
          print(f"[clicky] config error: {result.config_error}", file=sys.stderr)
      else:
          assert result.config is not None
          print(f"[clicky] config loaded: worker_url={result.config.worker_url}")
      return 0


  if __name__ == "__main__":
      raise SystemExit(main())
  ```

- [ ] **Step 3:** Manual verification:
  - Delete `%APPDATA%\ClickyWin\config.toml` if it exists.
  - Run `uv run python -m clicky` from `clicky-py/`.
  - Expected: prints "first run: created config at ..." then "config error: worker_url is still the placeholder value..." then exits.
  - Edit `%APPDATA%\ClickyWin\config.toml` and change `worker_url` to `https://test.workers.dev`.
  - Run again. Expected: prints "config loaded: worker_url=https://test.workers.dev" and exits.

- [ ] **Step 4:** Commit:
  ```bash
  git add clicky-py/clicky/app.py clicky-py/clicky/__main__.py
  git commit -m "feat(clicky-py): bootstrap QApplication and resolve config via platformdirs"
  ```

---

### Task 1.4: `VoiceState` enum and state broadcaster [IMPL]

**Files:**
- Create: `clicky-py/clicky/state.py`

Reference: Swift `CompanionManager.swift` — look for the voice state enum (likely `VoiceState` or similar with `idle | listening | processing | responding` cases).

**Steps:**

- [ ] **Step 1:** Create `clicky-py/clicky/state.py`:
  ```python
  """VoiceState enum — the high-level phase the companion is currently in."""

  from __future__ import annotations

  from enum import Enum


  class VoiceState(str, Enum):
      IDLE = "idle"
      LISTENING = "listening"
      PROCESSING = "processing"
      RESPONDING = "responding"
  ```

- [ ] **Step 2:** Commit:
  ```bash
  git add clicky-py/clicky/state.py
  git commit -m "feat(clicky-py): add VoiceState enum"
  ```

---

### Task 1.5: `TrayIcon` with state-colored programmatic icon [IMPL]

**Files:**
- Create: `clicky-py/clicky/icon_factory.py`
- Create: `clicky-py/clicky/ui/__init__.py`
- Create: `clicky-py/clicky/ui/tray_icon.py`

Reference: PRD § Question 14 decision 6 (tray icon color changes by state, no animation).

**Steps:**

- [ ] **Step 1:** Create `clicky-py/clicky/icon_factory.py` — a programmatic icon generator that draws a solid circle with a single-letter "C" glyph in the center using Pillow, configurable by fill color. Returns a `QIcon` built from an in-memory PNG. 32×32 base size, render at 64×64 and downscale for HiDPI smoothness. Color palette: idle=blue `#2E86FF`, listening=green `#28C76F`, responding=amber `#F5A623`, error=red `#EA5455`.

- [ ] **Step 2:** Create `clicky-py/clicky/ui/__init__.py` (empty).

- [ ] **Step 3:** Create `clicky-py/clicky/ui/tray_icon.py`:
  - `TrayIcon(QSystemTrayIcon)` subclass that holds a reference to the current `VoiceState` and rebuilds its icon via `icon_factory` whenever state changes.
  - Left-click (via `activated` signal with `Trigger` reason) emits a `toggle_panel_requested` signal.
  - Right-click menu has a single "Quit" action that calls `QApplication.instance().quit()`.
  - Tooltip shows "ClickyWin".

- [ ] **Step 4:** Manual verification will happen in Task 1.7 when we wire it up. For now, commit the module.

- [ ] **Step 5:** Commit:
  ```bash
  git add clicky-py/clicky/icon_factory.py clicky-py/clicky/ui/__init__.py clicky-py/clicky/ui/tray_icon.py
  git commit -m "feat(clicky-py): add programmatic tray icon with state-based colors"
  ```

---

### Task 1.6: `Panel` frameless window skeleton with tray-anchor positioning [IMPL]

**Files:**
- Create: `clicky-py/clicky/ui/panel.py`

Reference: Swift `MenuBarPanelManager.swift` (panel positioning near status item) and `CompanionPanelView.swift` (panel content). PRD § Q14c5 (panel behavior).

**Steps:**

- [ ] **Step 1:** Create `clicky-py/clicky/ui/panel.py`:
  - `Panel(QWidget)` — frameless (`Qt.WindowType.FramelessWindowHint`), `Qt.WindowType.Tool`, `Qt.WindowType.WindowStaysOnTopHint`, `Qt.WidgetAttribute.WA_TranslucentBackground`, dark-themed rounded background drawn in `paintEvent`.
  - Minimum size 420×360. Corner radius 16 px to match CursorBuddy's recent panel update.
  - Placeholder label "ClickyWin — Hold Ctrl+Alt to talk" vertically centered.
  - `show_near_tray(tray_icon: TrayIcon)` method: reads the tray icon's `geometry()`, positions the panel just above/below it (within screen bounds), and shows itself.
  - Click-outside-to-dismiss: install a `QApplication.instance().installEventFilter(self)` that watches for `MouseButtonPress` events outside the panel's frame while visible, hiding on outside click.
  - Escape key hides the panel.

- [ ] **Step 2:** Commit:
  ```bash
  git add clicky-py/clicky/ui/panel.py
  git commit -m "feat(clicky-py): add frameless dark panel with tray-anchor positioning"
  ```

---

### Task 1.7: `HotkeyMonitor` with strict modifier-only Ctrl+Alt detection [IMPL]

**Files:**
- Create: `clicky-py/clicky/hotkey.py`

Reference: Swift `GlobalPushToTalkShortcutMonitor.swift`. PRD § Question 5c (strict modifier-only semantics).

**Steps:**

- [ ] **Step 1:** Open `leanring-buddy/GlobalPushToTalkShortcutMonitor.swift` and confirm the press/release semantics match what we specified (strict modifier-only, cancel-on-other-key). If Farza's behavior differs, capture the difference in a comment inside `hotkey.py` and follow his behavior.

- [ ] **Step 2:** Create `clicky-py/clicky/hotkey.py`:
  - `HotkeyMonitor(QObject)` subclass. Constructor takes `binding: str` (values: `"ctrl+alt"` or `"right_ctrl"`).
  - Qt signals: `pressed = Signal()`, `released = Signal()`, `cancelled = Signal()`.
  - Internally runs a `pynput.keyboard.Listener` on a background thread.
  - Tracks a `set[str]` of currently-held normalized keys. Normalization maps `Key.ctrl_l → "ctrl_l"`, `Key.ctrl_r → "ctrl_r"`, `Key.alt_l / Key.alt_r / Key.alt_gr → "alt"`, `Key.cmd* → "win"`, other keys to their `.char` or `str(key)`.
  - Binding-specific trigger logic:
    - **`"ctrl+alt"`:** armed when both a ctrl key (`ctrl_l` OR `ctrl_r`) and `alt` are in the held set AND nothing else (no non-modifier keys) is held.
    - **`"right_ctrl"`:** armed when only `ctrl_r` is in the held set AND nothing else (no other modifier, no non-modifier) is held.
  - State machine (same for both bindings): `UNARMED` → (arming condition met) → emit `pressed`, enter `ARMED` → (any non-modifier key pressed while armed) → emit `cancelled`, enter `CANCELLED` → (all modifiers released) → back to `UNARMED`. From `ARMED`: releasing any required modifier → emit `released`, back to `UNARMED`.
  - Signal emission is thread-safe: use `QMetaObject.invokeMethod(obj, "method_name", Qt.ConnectionType.QueuedConnection)` or `QTimer.singleShot(0, lambda: self.pressed.emit())` to hop back to the main thread.
  - `start()` creates and starts the listener. `stop()` stops it. Unknown binding values raise `ValueError` at construction (not `NotImplementedError` — the set is closed in v1).

- [ ] **Step 3:** Commit:
  ```bash
  git add clicky-py/clicky/hotkey.py
  git commit -m "feat(clicky-py): add strict modifier-only hotkey monitor via pynput"
  ```

---

### Task 1.8: Wire tray + panel + hotkey together in `app.py`, manually verify Phase 1 [IMPL]

**Files:**
- Modify: `clicky-py/clicky/app.py`
- Modify: `clicky-py/clicky/__main__.py`

**Steps:**

- [ ] **Step 1:** Add a `run()` function to `clicky-py/clicky/app.py` that:
  - Calls `bootstrap()`.
  - If config_error is set, prints it to stderr and proceeds anyway (panel will later show a banner; for Phase 1, just log).
  - Creates `TrayIcon(initial_state=VoiceState.IDLE)`.
  - Creates `Panel()`.
  - Connects `tray_icon.toggle_panel_requested` to a handler that toggles `panel.show_near_tray(tray_icon)` / `panel.hide()`.
  - Creates `HotkeyMonitor(hotkey=config.hotkey if config else "ctrl+alt")`.
  - Connects `hotkey_monitor.pressed` to a handler that prints `"[clicky] hotkey pressed"` AND calls `panel.show_near_tray(tray_icon)`.
  - Connects `hotkey_monitor.released` to a handler that prints `"[clicky] hotkey released"`.
  - Connects `hotkey_monitor.cancelled` to a handler that prints `"[clicky] hotkey cancelled"`.
  - Starts the hotkey monitor.
  - Shows the tray icon.
  - If `was_first_run`, immediately calls `panel.show_near_tray(tray_icon)`.
  - Returns `app.exec()`.

- [ ] **Step 2:** Update `__main__.py` to call `run()` instead of the Phase 1 debug prints.

- [ ] **Step 3:** Manual verification (**you must actually run the app for this**):
  - Run `uv run python -m clicky` from `clicky-py/`.
  - Expected: a tray icon appears with a blue "C" on a colored circle.
  - Expected (if you deleted config first): panel auto-opens near the tray.
  - Click the tray icon. Expected: panel toggles show/hide.
  - With the panel hidden, press and HOLD Ctrl+Alt (no other keys). Expected: stderr shows "hotkey pressed" and the panel opens. Release either key: stderr shows "hotkey released".
  - Press Ctrl+Alt+C (i.e., press C while holding both). Expected: stderr shows "hotkey pressed" then "hotkey cancelled". The normal Ctrl+Alt+C system behavior (copy in some contexts) should still work in the foreground app.
  - Click outside the panel. Expected: panel hides.
  - Right-click tray → Quit. Expected: app exits cleanly.

- [ ] **Step 4:** If all expected behaviors work, commit:
  ```bash
  git add clicky-py/clicky/app.py clicky-py/clicky/__main__.py
  git commit -m "feat(clicky-py): wire tray, panel, and hotkey for phase 1 milestone"
  ```

**Phase 1 milestone reached:** app runs, tray works, panel opens/closes on tray click and hotkey press, strict modifier-only detection works, config loads and creates on first run.

---

## Phase 2: Mic capture + live waveform

**Milestone:** Pressing and holding Ctrl+Alt starts mic capture; the panel shows a live waveform reacting to your voice; releasing the hotkey stops capture.

---

### Task 2.1: `MicCapture` with `sounddevice` WASAPI stream [IMPL]

**Files:**
- Create: `clicky-py/clicky/mic_capture.py`

Reference: Swift `BuddyDictationManager.swift` and `BuddyAudioConversionSupport.swift`. PRD § Question 6a + 6c (sounddevice, 16 kHz PCM16 mono, 100 ms chunks).

**Steps:**

- [ ] **Step 1:** Open `leanring-buddy/BuddyAudioConversionSupport.swift` and confirm the exact sample rate and chunk size Farza uses. If it differs from 16 kHz / 100 ms, match his numbers and add a comment in the Python file explaining why.

- [ ] **Step 2:** Create `clicky-py/clicky/mic_capture.py`:
  - `MicCapture(QObject)` subclass.
  - Qt signals: `pcm_chunk = Signal(bytes)`, `audio_level = Signal(float)`, `error = Signal(str)`.
  - Internal state: `sounddevice.InputStream` with `samplerate=16000, channels=1, dtype='int16', blocksize=1600` (100 ms at 16 kHz).
  - `start()`: opens the stream with a callback that, on each block:
    1. Copies the numpy int16 buffer to bytes via `indata.tobytes()` — the numpy array passed to the callback is invalidated after the callback returns, so you MUST copy before emitting the signal.
    2. Computes RMS: `rms = min(math.sqrt(np.mean(indata.astype(np.float32) ** 2)) / 32768.0, 1.0)` — explicitly clamped because a peak int16 sample of −32768 would otherwise exceed 1.0.
    3. Emits `pcm_chunk(bytes)` and `audio_level(rms)`. Use `QMetaObject.invokeMethod` or a thread-safe Qt Signal-Slot queued connection to marshal to the main thread.
  - `stop()`: stops and closes the stream.
  - Handles `sounddevice.PortAudioError` by emitting `error("microphone unavailable — check privacy settings")`.

- [ ] **Step 3:** Commit:
  ```bash
  git add clicky-py/clicky/mic_capture.py
  git commit -m "feat(clicky-py): add sounddevice mic capture with PCM16 streaming"
  ```

---

### Task 2.2: `WaveformView` custom paint widget [IMPL]

**Files:**
- Create: `clicky-py/clicky/ui/waveform_view.py`

Reference: PRD § Question 14 waveform implementation sketch.

**Steps:**

- [ ] **Step 1:** Create `clicky-py/clicky/ui/waveform_view.py`:
  - `WaveformView(QWidget)` subclass.
  - `__init__`: creates `collections.deque(maxlen=60)` of RMS values, creates a `QTimer(16)` (~60 FPS) that calls `self.update()` while the widget is visible.
  - Slot: `@Slot(float) def push_level(level: float)` appends to the deque.
  - `paintEvent`: draws 60 vertical bars spread across the widget width; each bar height is proportional to `level * widget_height * 0.9`, centered vertically, colored with `DS.Colors.ACCENT_BLUE` (define in design_system later; for now hardcode `QColor("#2E86FF")`). Use `QPainter` with antialiasing.
  - `start()` / `stop()` methods: start/stop the internal QTimer so it's not wasting CPU while the widget is hidden.
  - Default minimum size 360×72.

- [ ] **Step 2:** Commit:
  ```bash
  git add clicky-py/clicky/ui/waveform_view.py
  git commit -m "feat(clicky-py): add custom waveform view with 60fps paint loop"
  ```

---

### Task 2.3: Wire `MicCapture` ↔ `WaveformView` via `Panel`, Phase 2 manual verify [IMPL]

**Files:**
- Modify: `clicky-py/clicky/ui/panel.py`
- Modify: `clicky-py/clicky/app.py`

**Steps:**

- [ ] **Step 1:** Update `clicky-py/clicky/ui/panel.py`:
  - Embed a `WaveformView` instance in the panel layout. Hidden by default; shown when state becomes `LISTENING`.
  - Add `set_state(state: VoiceState)` method: shows waveform for `LISTENING`, hides for other states. Starts/stops the waveform's internal timer accordingly.
  - Add `set_audio_level(level: float)` method that forwards to `waveform.push_level(level)`.

- [ ] **Step 2:** Update `clicky-py/clicky/app.py` `run()`:
  - Create `MicCapture()` instance.
  - Connect `hotkey.pressed` → `mic.start()` AND `panel.set_state(VoiceState.LISTENING)` AND `panel.show_near_tray(tray)`.
  - Connect `hotkey.released` → `mic.stop()` AND `panel.set_state(VoiceState.IDLE)`.
  - Connect `hotkey.cancelled` → `mic.stop()` AND `panel.set_state(VoiceState.IDLE)`.
  - Connect `mic.audio_level` → `panel.set_audio_level`.
  - Connect `mic.error` → `print` to stderr (replaced with banner in Phase 6).

- [ ] **Step 3:** Manual verification:
  - Run `uv run python -m clicky`.
  - Press and hold Ctrl+Alt. Panel opens. **Speak into your mic.** Expected: waveform bars react to your voice, growing with volume and falling during silence.
  - Release either key. Expected: waveform disappears, panel state returns to idle.
  - Open Settings → Privacy → Microphone → Microphone access → toggle OFF. Re-run app and press hotkey. Expected: stderr shows mic error. Re-enable mic access.

- [ ] **Step 4:** Commit:
  ```bash
  git add clicky-py/clicky/ui/panel.py clicky-py/clicky/app.py
  git commit -m "feat(clicky-py): connect mic capture to live waveform in panel"
  ```

**Phase 2 milestone reached:** live audio feedback works end-to-end.

---

## Phase 3: AssemblyAI streaming transcription

**Milestone:** Pressing Ctrl+Alt, speaking, and releasing shows the finalized transcript in the panel. Interim transcripts appear live as you speak.

---

### Task 3.1: Deploy Cloudflare Worker (operator action, not code) [IMPL]

**Files:** No code changes. This is a checklist.

**Steps:**

- [ ] **Step 1:** From `worker/`, run `npm install`.
- [ ] **Step 2:** Run `npx wrangler login` if not already logged in.
- [ ] **Step 3:** Run `npx wrangler secret put ANTHROPIC_API_KEY` and paste your key.
- [ ] **Step 4:** Run `npx wrangler secret put ASSEMBLYAI_API_KEY` and paste your key.
- [ ] **Step 5:** Run `npx wrangler secret put ELEVENLABS_API_KEY` and paste your key.
- [ ] **Step 6:** Open `worker/wrangler.toml`. Replace the placeholder `ELEVENLABS_VOICE_ID` with your own ElevenLabs voice ID (found at elevenlabs.io → Voice Lab). If you don't have one yet, skip and Claude will still work — only TTS will fail until you set it.
- [ ] **Step 7:** In `worker/wrangler.toml`, change the worker `name` field to `clicky-win-proxy`. **Note:** this edits an upstream-tracked file. It's a local tweak, not a disruptive reorganization. If you prefer not to touch the tracked file, create a `worker/wrangler.clickywin.toml` override and pass it via `--config` in the deploy command.
- [ ] **Step 8:** Run `npx wrangler deploy`. Note the output URL (e.g. `https://clicky-win-proxy.<your-subdomain>.workers.dev`).
- [ ] **Step 9:** Edit `%APPDATA%\ClickyWin\config.toml` and set `worker_url` to the deployed URL.
- [ ] **Step 10:** Smoke-test each route with curl:
  ```bash
  curl -X POST https://clicky-win-proxy.<your-subdomain>.workers.dev/transcribe-token
  # Expected: JSON with "token" field
  ```
- [ ] **Step 11:** No commit — this task has no files to commit. Mark it done when the smoke test succeeds.

---

### Task 3.2: `TranscriptionClient` message parser [TDD]

**Files:**
- Create: `clicky-py/clicky/clients/__init__.py`
- Create: `clicky-py/clicky/clients/transcription_client.py`
- Create: `clicky-py/tests/test_transcription_parser.py`
- Create: `clicky-py/tests/fixtures/assemblyai_v3_messages.json`

Reference: Swift `AssemblyAIStreamingTranscriptionProvider.swift` — note the exact JSON shape of AssemblyAI v3 messages. Open it and record at least 3 representative message types as fixtures.

**Steps:**

- [ ] **Step 1:** Open `leanring-buddy/AssemblyAIStreamingTranscriptionProvider.swift` and identify the v3 message types the Swift client handles. Common v3 message types include: `{"type":"Begin","id":...}`, `{"type":"Turn","transcript":"...","end_of_turn":false}`, `{"type":"Turn","transcript":"...","end_of_turn":true}`, `{"type":"Termination",...}`. Record actual examples as fixture JSON in `clicky-py/tests/fixtures/assemblyai_v3_messages.json` as a list of message objects, one per representative case.

- [ ] **Step 2:** Create `clicky-py/clicky/clients/__init__.py` (empty).

- [ ] **Step 3:** Write failing tests in `clicky-py/tests/test_transcription_parser.py`:
  ```python
  import json
  from pathlib import Path

  from clicky.clients.transcription_client import (
      TranscriptEvent,
      parse_assemblyai_message,
  )

  FIXTURE = Path(__file__).parent / "fixtures" / "assemblyai_v3_messages.json"


  def test_parses_begin_message_as_none() -> None:
      messages = json.loads(FIXTURE.read_text())
      begin = next(m for m in messages if m["type"] == "Begin")
      event = parse_assemblyai_message(begin)
      assert event is None  # Begin messages are not user-facing events


  def test_parses_interim_turn_as_interim_event() -> None:
      messages = json.loads(FIXTURE.read_text())
      interim = next(
          m for m in messages if m["type"] == "Turn" and not m.get("end_of_turn")
      )
      event = parse_assemblyai_message(interim)
      assert isinstance(event, TranscriptEvent)
      assert event.is_final is False
      assert event.text == interim["transcript"]


  def test_parses_final_turn_as_final_event() -> None:
      messages = json.loads(FIXTURE.read_text())
      final = next(
          m for m in messages if m["type"] == "Turn" and m.get("end_of_turn")
      )
      event = parse_assemblyai_message(final)
      assert isinstance(event, TranscriptEvent)
      assert event.is_final is True
      assert event.text == final["transcript"]


  def test_ignores_unknown_message_type() -> None:
      event = parse_assemblyai_message({"type": "SomeFutureMessage", "foo": "bar"})
      assert event is None


  def test_ignores_termination_message() -> None:
      event = parse_assemblyai_message({"type": "Termination"})
      assert event is None
  ```

- [ ] **Step 4:** Run `uv run pytest tests/test_transcription_parser.py -v`. Expected: tests fail with import error.

- [ ] **Step 5:** Create the minimal parser in `clicky-py/clicky/clients/transcription_client.py` — just the `TranscriptEvent` dataclass and the `parse_assemblyai_message(msg: dict) -> TranscriptEvent | None` function. Do NOT implement the websocket yet; that's the next task.

- [ ] **Step 6:** Run tests. Expected: all pass.

- [ ] **Step 7:** Commit:
  ```bash
  git add clicky-py/clicky/clients/__init__.py clicky-py/clicky/clients/transcription_client.py clicky-py/tests/test_transcription_parser.py clicky-py/tests/fixtures/assemblyai_v3_messages.json
  git commit -m "feat(clicky-py): add AssemblyAI v3 message parser with fixtures"
  ```

---

### Task 3.3: `TranscriptionClient` websocket lifecycle [IMPL]

**Files:**
- Modify: `clicky-py/clicky/clients/transcription_client.py`

Reference: Swift `AssemblyAIStreamingTranscriptionProvider.swift` for the token dance, URL format, binary frame protocol, and reconnect strategy.

**Steps:**

- [ ] **Step 1:** Extend `transcription_client.py` with a `TranscriptionClient(QObject)` class:
  - Qt signals: `interim_transcript = Signal(str)`, `final_transcript = Signal(str)`, `error = Signal(str)`.
  - Constructor takes `worker_url: str`.
  - `start_stream(pcm_chunk_iterator)` method (async) that:
    1. Fetches a token via `httpx.AsyncClient.post(f"{worker_url}/transcribe-token")`.
    2. Opens a websocket to `wss://streaming.assemblyai.com/v3/ws?token=<token>&sample_rate=16000&encoding=pcm_s16le` (cross-check against Swift source for exact query-parameter spelling).
    3. Concurrently runs two tasks: **send-loop** consumes PCM chunks from the iterator and sends them as binary frames; **recv-loop** receives JSON text messages, parses with `parse_assemblyai_message`, emits signals for non-`None` events. Recv-loop tracks the most recent final `Turn` message seen so `stop_stream` can surface it.
    4. On any exception, emits `error(str(exc))` and returns.
    5. One auto-reconnect attempt on websocket connection drop mid-stream (before giving up).
  - `stop_stream()` method (async) implements a **graceful drain contract**, not a hard cancel:
    1. Stop feeding new PCM to the send-loop (the iterator signals completion).
    2. Send a termination frame to AssemblyAI — the v3 protocol uses `{"type":"Terminate"}` as a text JSON message. Cross-check against `leanring-buddy/AssemblyAIStreamingTranscriptionProvider.swift` for the exact shape.
    3. Await the recv-loop until either the final `Turn` message arrives (with `end_of_turn=True`) OR a 2-second bounded timeout elapses — whichever comes first.
    4. Cancel the recv-loop task if the timeout wins and log a warning; otherwise let it complete naturally.
    5. Close the websocket.
    6. If no final transcript was ever received, emit `final_transcript("")` so the `CompanionManager` can decide to abort the turn silently (empty-transcript rule from Task 4.8).
  - Use `asyncio` + `qasync` bridging so coroutines can be kicked off from Qt signal handlers. Add `qasync>=0.27` to `pyproject.toml` dependencies and `uv sync`.

- [ ] **Step 2:** Commit:
  ```bash
  git add clicky-py/clicky/clients/transcription_client.py clicky-py/pyproject.toml clicky-py/uv.lock
  git commit -m "feat(clicky-py): add AssemblyAI v3 streaming websocket client"
  ```

---

### Task 3.4: `TranscriptView` widget [IMPL]

**Files:**
- Create: `clicky-py/clicky/ui/transcript_view.py`

**Steps:**

- [ ] **Step 1:** Create `clicky-py/clicky/ui/transcript_view.py`:
  - `TranscriptView(QWidget)` with a `QLabel` that displays two lines:
    - Interim transcript in gray italic
    - Final transcript in white regular weight
  - Slots: `@Slot(str) def set_interim(text: str)`, `@Slot(str) def set_final(text: str)`, `@Slot() def clear()`.
  - Minimum size 360×72, word wrap enabled.

- [ ] **Step 2:** Commit:
  ```bash
  git add clicky-py/clicky/ui/transcript_view.py
  git commit -m "feat(clicky-py): add transcript view for interim + final text"
  ```

---

### Task 3.5: Wire transcription into panel and app orchestration, Phase 3 manual verify [IMPL]

**Files:**
- Modify: `clicky-py/clicky/ui/panel.py`
- Modify: `clicky-py/clicky/app.py`

**Steps:**

- [ ] **Step 1:** Add `TranscriptView` to panel layout below the waveform. Shown during `LISTENING` and `PROCESSING` states.

- [ ] **Step 2:** In `app.py`:
  - Install `qasync` event loop integration with the `QApplication`.
  - Create `TranscriptionClient(worker_url=config.worker_url)`.
  - Maintain a `deque` of PCM chunks between `mic.pcm_chunk` signal and `TranscriptionClient.start_stream(async_generator_over_deque)`.
  - On `hotkey.pressed`: start mic, call `asyncio.create_task(transcription.start_stream(...))`.
  - On `hotkey.released`: stop mic, call `transcription.stop_stream()`.
  - Connect `transcription.interim_transcript` → `panel.transcript.set_interim`.
  - Connect `transcription.final_transcript` → `panel.transcript.set_final` AND log to stderr.
  - Connect `transcription.error` → stderr log (banner comes in Phase 6).

- [ ] **Step 3:** Manual verification:
  - Run `uv run python -m clicky`.
  - Hold Ctrl+Alt, say *"testing one two three, can you hear me?"*, release.
  - Expected: interim transcript appears in the panel as you speak; final transcript replaces it on release. Stderr logs the final text.
  - Disconnect from wifi, try again. Expected: stderr logs a transcription error.

- [ ] **Step 4:** Commit:
  ```bash
  git add clicky-py/clicky/ui/panel.py clicky-py/clicky/app.py
  git commit -m "feat(clicky-py): wire AssemblyAI transcription into phase 3 flow"
  ```

**Phase 3 milestone reached:** voice → transcript round-trip works.

---

## Phase 4: Screen capture + Claude streaming response

**Milestone:** Pressing Ctrl+Alt, speaking a question about what's on your screen, and releasing shows a streaming text response from Claude in the panel.

---

### Task 4.1: `ScreenCapture` label composer [TDD]

**Files:**
- Create: `clicky-py/tests/test_screen_capture_labels.py`
- Create: `clicky-py/clicky/screen_capture.py`

Reference: Swift `CompanionScreenCaptureUtility.swift` lines 104–111 for the exact label strings.

**Steps:**

- [ ] **Step 1:** Write failing tests in `clicky-py/tests/test_screen_capture_labels.py`:
  ```python
  from clicky.screen_capture import compose_screen_label


  def test_single_screen_label() -> None:
      label = compose_screen_label(
          screen_index=0, total_screens=1, is_cursor_screen=True
      )
      assert label == "user's screen (cursor is here)"


  def test_cursor_screen_label_multi() -> None:
      label = compose_screen_label(
          screen_index=0, total_screens=2, is_cursor_screen=True
      )
      assert label == "screen 1 of 2 — cursor is on this screen (primary focus)"


  def test_secondary_screen_label_multi() -> None:
      label = compose_screen_label(
          screen_index=1, total_screens=2, is_cursor_screen=False
      )
      assert label == "screen 2 of 2 — secondary screen"


  def test_three_screens_numbering() -> None:
      assert (
          compose_screen_label(
              screen_index=2, total_screens=3, is_cursor_screen=False
          )
          == "screen 3 of 3 — secondary screen"
      )
  ```

- [ ] **Step 2:** Run tests. Expected: fail with import error.

- [ ] **Step 3:** Create `clicky-py/clicky/screen_capture.py` with just the `compose_screen_label(screen_index, total_screens, is_cursor_screen) -> str` function matching Farza's strings exactly. Do not implement the `capture()` function yet.

- [ ] **Step 4:** Run tests. Expected: pass.

- [ ] **Step 5:** Commit:
  ```bash
  git add clicky-py/clicky/screen_capture.py clicky-py/tests/test_screen_capture_labels.py
  git commit -m "feat(clicky-py): add screen capture label composer"
  ```

---

### Task 4.2: `ScreenCapture.capture()` via `mss` + Pillow downscale [IMPL]

**Files:**
- Modify: `clicky-py/clicky/screen_capture.py`
- Modify: `clicky-py/clicky/app.py` (add DPI awareness call)

Reference: Swift `CompanionScreenCaptureUtility.swift` for the 1280-px long-edge downscale and JPEG 0.8 config.

**Steps:**

- [ ] **Step 1:** In `app.py`, at the very top of `bootstrap()` (before `QApplication` creation), add:
  ```python
  import ctypes
  import sys

  if sys.platform == "win32":
      try:
          # PROCESS_PER_MONITOR_DPI_AWARE (v1) is sufficient for our use case:
          # mss captures at raw physical pixels regardless of v1/v2, and Qt's
          # widget rendering is handled by PySide6's own Qt::AA_EnableHighDpiScaling.
          # If we later need per-monitor v2 for the overlay window in v2, switch
          # to user32.SetProcessDpiAwarenessContext(-4).
          ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
      except (AttributeError, OSError):
          pass
  ```
  This is critical — it must run before any Qt or mss calls.

- [ ] **Step 2:** Extend `screen_capture.py`:
  - Add a `@dataclass class ScreenshotImage` with fields: `jpeg_bytes: bytes`, `label: str`, `is_cursor_screen: bool`, `display_width_px: int`, `display_height_px: int`, `image_width_px: int`, `image_height_px: int`.
  - Add `capture_all() -> list[ScreenshotImage]` function that:
    1. Uses `pynput.mouse.Controller().position` to get the virtual-screen cursor coordinates.
    2. Opens `mss.mss()` and iterates `sct.monitors[1:]` (index 0 is the virtual screen aggregate).
    3. For each monitor, determines if the cursor is inside its bounds.
    4. Sorts monitors so the cursor-screen comes first, matching Farza's Swift code.
    5. For each monitor: grabs the raw BGRA pixels via `sct.grab(monitor)`, converts to a Pillow `Image`, downscales so the long edge is ≤ 1280 px (preserving aspect ratio), encodes as JPEG quality 80.
    6. Returns a list of `ScreenshotImage` objects with correct labels via `compose_screen_label`.

- [ ] **Step 3:** Manual verification: add a temporary test harness that saves the JPEGs to disk so you can open them and verify they look right. Run, inspect, delete the test harness before committing.

- [ ] **Step 4:** Commit:
  ```bash
  git add clicky-py/clicky/screen_capture.py clicky-py/clicky/app.py
  git commit -m "feat(clicky-py): add multi-monitor screen capture with 1280px JPEG downscale"
  ```

---

### Task 4.3: `ConversationHistory` module [TDD]

**Files:**
- Create: `clicky-py/clicky/conversation_history.py`
- Create: `clicky-py/tests/test_conversation_history.py`

Reference: PRD § Implementation Decisions → ConversationHistory.

**Steps:**

- [ ] **Step 1:** Write failing tests in `clicky-py/tests/test_conversation_history.py`:
  ```python
  from clicky.conversation_history import ConversationHistory, MAX_TURNS


  def test_append_and_count() -> None:
      history = ConversationHistory()
      history.append("hi", "hello")
      history.append("what", "thing")
      assert history.turn_count() == 2


  def test_caps_at_max_turns() -> None:
      history = ConversationHistory()
      for i in range(MAX_TURNS + 5):
          history.append(f"q{i}", f"a{i}")
      assert history.turn_count() == MAX_TURNS
      # Oldest turns should be dropped, newest kept
      messages = history.messages_for_request(
          current_user_text="current", current_images=[]
      )
      # First prior-turn message should be q5 / a5, not q0
      first_user = messages[0]
      assert first_user["role"] == "user"
      assert first_user["content"] == "q5"


  def test_messages_for_request_puts_images_on_current_only() -> None:
      history = ConversationHistory()
      history.append("prev-q", "prev-a")
      fake_image = {"type": "image", "source": {"data": "...", "media_type": "image/jpeg"}}
      messages = history.messages_for_request(
          current_user_text="now", current_images=[fake_image]
      )
      # Prior turn is text-only
      assert messages[0] == {"role": "user", "content": "prev-q"}
      assert messages[1] == {"role": "assistant", "content": "prev-a"}
      # Current turn has images AND text
      current = messages[2]
      assert current["role"] == "user"
      assert isinstance(current["content"], list)
      content_types = [block.get("type") for block in current["content"]]
      assert "image" in content_types
      assert "text" in content_types


  def test_empty_history_only_current_turn() -> None:
      history = ConversationHistory()
      messages = history.messages_for_request(
          current_user_text="first question", current_images=[]
      )
      assert len(messages) == 1
      assert messages[0]["role"] == "user"
  ```

- [ ] **Step 2:** Run tests. Expected: fail.

- [ ] **Step 3:** Implement `clicky-py/clicky/conversation_history.py`:
  ```python
  """In-memory conversation history for the Claude client.

  Keeps a capped list of (user_transcript, assistant_text) tuples. Composes
  Claude message arrays where prior turns are text-only and only the current
  turn carries JPEG images — matching Farza's swift implementation and
  controlling token cost.
  """

  from __future__ import annotations

  from collections import deque
  from typing import Any

  MAX_TURNS = 20


  class ConversationHistory:
      def __init__(self) -> None:
          self._turns: deque[tuple[str, str]] = deque(maxlen=MAX_TURNS)

      def append(self, user_text: str, assistant_text: str) -> None:
          self._turns.append((user_text, assistant_text))

      def turn_count(self) -> int:
          return len(self._turns)

      def clear(self) -> None:
          self._turns.clear()

      def messages_for_request(
          self,
          current_user_text: str,
          current_images: list[dict[str, Any]],
      ) -> list[dict[str, Any]]:
          messages: list[dict[str, Any]] = []
          # Prior turns: text-only, to keep token/cost footprint sane.
          for user_text, assistant_text in self._turns:
              messages.append({"role": "user", "content": user_text})
              messages.append({"role": "assistant", "content": assistant_text})
          # Current turn: text + images as content blocks.
          if current_images:
              content = [*current_images, {"type": "text", "text": current_user_text}]
          else:
              content = current_user_text
          messages.append({"role": "user", "content": content})
          return messages
  ```

- [ ] **Step 4:** Run tests. Expected: pass.

- [ ] **Step 5:** Commit:
  ```bash
  git add clicky-py/clicky/conversation_history.py clicky-py/tests/test_conversation_history.py
  git commit -m "feat(clicky-py): add 20-turn conversation history with images-on-current-turn rule"
  ```

---

### Task 4.4: `LLMClient` SSE parser [TDD]

**Files:**
- Create: `clicky-py/clicky/clients/llm_client.py`
- Create: `clicky-py/tests/test_llm_sse_parser.py`
- Create: `clicky-py/tests/fixtures/anthropic_sse_basic.txt`
- Create: `clicky-py/tests/fixtures/anthropic_sse_unknown_block.txt`

Reference: Anthropic streaming documentation + Swift `ClaudeAPI.swift`. Record actual SSE bytes from a real API call if possible; otherwise craft representative fixtures.

**Steps:**

- [ ] **Step 1:** Create the fixture files. `anthropic_sse_basic.txt` should contain a full SSE stream with: `message_start`, `content_block_start` (text), multiple `content_block_delta` (text_delta) events, `content_block_stop`, `message_delta`, `message_stop`. `anthropic_sse_unknown_block.txt` should contain an SSE stream with a `content_block_start` carrying an unknown `type` (e.g. `"type": "some_future_block"`), a delta for it, and its stop event, followed by a normal text block — to verify defensive parsing.

- [ ] **Step 2:** Write failing tests in `clicky-py/tests/test_llm_sse_parser.py`:
  ```python
  from pathlib import Path

  from clicky.clients.llm_client import parse_anthropic_sse_stream

  FIXTURES = Path(__file__).parent / "fixtures"


  def test_basic_stream_yields_text_deltas() -> None:
      raw = (FIXTURES / "anthropic_sse_basic.txt").read_bytes()
      deltas = list(parse_anthropic_sse_stream(raw))
      joined = "".join(deltas)
      assert len(joined) > 0
      assert deltas[0] != ""


  def test_unknown_block_types_are_ignored_not_crashed() -> None:
      raw = (FIXTURES / "anthropic_sse_unknown_block.txt").read_bytes()
      deltas = list(parse_anthropic_sse_stream(raw))
      # Unknown blocks must not raise — they are silently skipped.
      # The known text block inside the fixture should still produce deltas.
      joined = "".join(deltas)
      assert "hello" in joined.lower() or len(joined) > 0


  def test_empty_stream_yields_nothing() -> None:
      assert list(parse_anthropic_sse_stream(b"")) == []
  ```

- [ ] **Step 3:** Run tests. Expected: fail with import error.

- [ ] **Step 4:** Implement `parse_anthropic_sse_stream(raw: bytes) -> Iterator[str]` in `clicky-py/clicky/clients/llm_client.py`:
  - Parse SSE events (`event: <name>\ndata: <json>\n\n` blocks).
  - For each `content_block_delta` event, check the delta type. If `text_delta`, yield `delta["text"]`. If unknown type, skip silently.
  - For `content_block_start` events, track the current block's `type` — if unknown, flag the block so its deltas are also ignored.
  - Ignore `message_start`, `message_delta`, `message_stop`, `ping`, `content_block_stop`.

- [ ] **Step 5:** Run tests. Expected: pass.

- [ ] **Step 6:** Commit:
  ```bash
  git add clicky-py/clicky/clients/llm_client.py clicky-py/tests/test_llm_sse_parser.py clicky-py/tests/fixtures/anthropic_sse_basic.txt clicky-py/tests/fixtures/anthropic_sse_unknown_block.txt
  git commit -m "feat(clicky-py): add Anthropic SSE parser with defensive unknown-block handling"
  ```

---

### Task 4.5: `LLMClient.send()` full streaming request [IMPL]

**Files:**
- Modify: `clicky-py/clicky/clients/llm_client.py`

Reference: Swift `ClaudeAPI.swift` for the request shape (endpoint path, headers, body structure).

**Steps:**

- [ ] **Step 1:** Extend `llm_client.py` with an `LLMClient(QObject)` class:
  - Qt signals: `delta = Signal(str)`, `done = Signal(str)` (full response), `error = Signal(str)`.
  - Constructor takes `worker_url: str`.
  - Method `async send(messages: list[dict], system: str, model: str, max_tokens: int = 1024) -> str`:
    1. Builds request body with `model`, `max_tokens`, `stream=True`, `system`, `messages`.
    2. POSTs to `f"{worker_url}/chat"` via `httpx.AsyncClient` with streaming response.
    3. Iterates over `response.aiter_bytes()`, accumulates into a buffer, passes completed SSE event blocks to `parse_anthropic_sse_stream`.
    4. For each text delta yielded, emits `delta(text)` and appends to a running full-response string.
    5. On completion, emits `done(full_text)` and returns it.
    6. On any exception, emits `error(str(exc))` and re-raises.
  - Support cancellation via `asyncio.CancelledError` (caller can `task.cancel()`).

- [ ] **Step 2:** Commit:
  ```bash
  git add clicky-py/clicky/clients/llm_client.py
  git commit -m "feat(clicky-py): add Claude streaming HTTP client over worker proxy"
  ```

---

### Task 4.6: System prompt constant with Windows-retargeted examples [IMPL]

**Files:**
- Create: `clicky-py/clicky/prompts.py`

Reference: Swift `CompanionManager.swift` lines 544–577 (the non-pointing portion of `companionVoiceResponseSystemPrompt`; the full string runs to line ~581 but the pointing section is cut in v1).

**Steps:**

- [ ] **Step 1:** Create `clicky-py/clicky/prompts.py`:
  ```python
  """System prompts for ClickyWin.

  Voice and style rules are ported verbatim from Farza's Clicky
  (leanring-buddy/CompanionManager.swift companionVoiceResponseSystemPrompt).
  The element-pointing section is deliberately removed for ClickyWin v1 because
  the floating cursor overlay that would render the [POINT:x,y] coordinates is
  deferred to v2. When the overlay ships, re-add the pointing section from
  Farza's prompt and update this module's docstring.

  Examples are retargeted from macOS apps (Final Cut, Xcode) to Windows apps
  (DaVinci Resolve, Blender, VS Code) matching the target "Windows learner new
  to a tool" persona.
  """

  COMPANION_VOICE_SYSTEM_PROMPT = """\
  you're clicky, a friendly always-on companion that lives in the user's system tray. the user just spoke to you via push-to-talk and you can see their screen(s). your reply will be spoken aloud via text-to-speech, so write the way you'd actually talk. this is an ongoing conversation — you remember everything they've said before.

  rules:
  - default to one or two sentences. be direct and dense. BUT if the user asks you to explain more, go deeper, or elaborate, then go all out — give a thorough, detailed explanation with no length limit.
  - all lowercase, casual, warm. no emojis.
  - write for the ear, not the eye. short sentences. no lists, bullet points, markdown, or formatting — just natural speech.
  - don't use abbreviations or symbols that sound weird read aloud. write "for example" not "e.g.", spell out small numbers.
  - if the user's question relates to what's on their screen, reference specific things you see.
  - if the screenshot doesn't seem relevant to their question, just answer the question directly.
  - you can help with anything — coding, writing, general knowledge, brainstorming.
  - never say "simply" or "just".
  - don't read out code verbatim. describe what the code does or what needs to change conversationally.
  - focus on giving a thorough, useful explanation. don't end with simple yes/no questions like "want me to explain more?" or "should i show you?" — those are dead ends that force the user to just say yes.
  - instead, when it fits naturally, end by planting a seed — mention something bigger or more ambitious they could try, a related concept that goes deeper, or a next-level technique that builds on what you just explained. make it something worth coming back for, not a question they'd just nod to. it's okay to not end with anything extra if the answer is complete on its own.
  - if you receive multiple screen images, the one labeled "primary focus" is where the cursor is — prioritize that one but reference others if relevant.
  """
  ```

- [ ] **Step 2:** Commit:
  ```bash
  git add clicky-py/clicky/prompts.py
  git commit -m "feat(clicky-py): add companion system prompt (windows-retargeted)"
  ```

---

### Task 4.7: `ResponseView` widget [IMPL]

**Files:**
- Create: `clicky-py/clicky/ui/response_view.py`

**Steps:**

- [ ] **Step 1:** Create `clicky-py/clicky/ui/response_view.py`:
  - `ResponseView(QWidget)` with a scrollable `QTextEdit` (read-only, transparent background) that displays Claude's streaming response.
  - Slots: `@Slot() def clear()`, `@Slot(str) def append_delta(text: str)`, `@Slot(str) def set_full(text: str)`.
  - Auto-scroll to bottom on new delta.
  - Minimum size 360×160, word wrap enabled.

- [ ] **Step 2:** Commit:
  ```bash
  git add clicky-py/clicky/ui/response_view.py
  git commit -m "feat(clicky-py): add streaming response view"
  ```

---

### Task 4.8: `CompanionManager` orchestration state machine [IMPL]

**Files:**
- Create: `clicky-py/clicky/companion_manager.py`

Reference: Swift `CompanionManager.swift` — this is the biggest port. Read the Swift file top to bottom first.

**Steps:**

- [ ] **Step 1:** Read `leanring-buddy/CompanionManager.swift` fully (it's ~1026 lines). Identify the state transitions, cancellation logic, and the method that ties transcription → screen capture → Claude → TTS together (likely `sendTranscriptToClaudeWithScreenshot`).

- [ ] **Step 2:** Create `clicky-py/clicky/companion_manager.py`:
  - `CompanionManager(QObject)` class.
  - Qt signals: `state_changed = Signal(VoiceState)`, `audio_level = Signal(float)`, `interim_transcript = Signal(str)`, `final_transcript = Signal(str)`, `response_delta = Signal(str)`, `response_complete = Signal(str)`, `success_turn_completed = Signal()`, `error = Signal(str)`.
  - Constructor takes `config: Config`, `mic: MicCapture`, `hotkey: HotkeyMonitor`, `transcription: TranscriptionClient`, `llm: LLMClient`, `screen_capture_fn: Callable[[], Awaitable[list[ScreenshotImage]]]`, `panel_visibility_controller: PanelVisibilityController`. TTS is added in Phase 5.
  - `PanelVisibilityController` is a tiny protocol with `hide_for_capture()` and `restore_after_capture()` methods. The `Panel` widget implements it: `hide_for_capture()` calls `self.setWindowOpacity(0.0)` and `QApplication.processEvents()` (pump the compositor), `restore_after_capture()` calls `self.setWindowOpacity(1.0)`. This satisfies PRD user story 19 — the panel must not appear in the screenshot sent to Claude.
  - Internal state: `_state: VoiceState`, `_current_task: asyncio.Task | None`, `_history: ConversationHistory`, `_current_model: str`, `_cancel_flag: bool`.
  - Method `set_model(model_id: str)`.
  - Event handlers:
    - `_on_hotkey_pressed()`: if state is not IDLE, interrupt (set `_cancel_flag=True`, cancel `_current_task`, stop TTS — TTS added Phase 5). Transition to LISTENING. Start mic. Start transcription stream.
    - `_on_hotkey_released()`: transition to PROCESSING. Stop mic. Call `transcription.stop_stream()` (which will drain and emit `final_transcript` per the contract in Task 3.3).
    - `_on_final_transcript(text: str)`: if text is empty, return to IDLE silently (no error, no Claude call — covers the "pressed and released without speaking" case). Otherwise:
        1. Set `_cancel_flag = False` for this new turn.
        2. Call `panel_visibility_controller.hide_for_capture()` to make the panel invisible.
        3. Call `screen_capture_fn()` to grab JPEGs — no await here since `mss` is sync; wrap in `asyncio.to_thread(...)` if we keep the async signature.
        4. Call `panel_visibility_controller.restore_after_capture()` to bring the panel back.
        5. Base64-encode each `ScreenshotImage.jpeg_bytes` and build Claude image content blocks: `{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":base64_str}}` with a preceding text block for the label.
        6. Build messages via `history.messages_for_request(current_user_text=text, current_images=image_blocks)`.
        7. Start `llm.send(...)` as a task stored in `_current_task`.
        8. Relay `llm.delta` signals through `response_delta` AS LONG AS `_cancel_flag` is False. If `_cancel_flag` flips True mid-stream, stop relaying.
        9. On `llm.done(full_text)`: **only if `_cancel_flag` is False**, append `(text, full_text)` to history AND emit `response_complete(full_text)`. If cancelled, DO NOT append to history and DO NOT emit complete.
        10. Transition to RESPONDING while streaming, then IDLE on completion or cancel. On successful completion, emit `success_turn_completed()` so banners can auto-clear.
    - `_on_hotkey_cancelled()`: same as released but the transcription will emit an empty final_transcript (because we never completed a turn).
    - `_on_error(msg: str)`: emit error, transition to IDLE. Do NOT emit `success_turn_completed`.
  - Wires all component signals in its `__init__`.

- [ ] **Step 3:** Commit:
  ```bash
  git add clicky-py/clicky/companion_manager.py
  git commit -m "feat(clicky-py): add CompanionManager orchestration (no TTS yet)"
  ```

---

### Task 4.9: Wire CompanionManager into app, Phase 4 manual verify [IMPL]

**Files:**
- Modify: `clicky-py/clicky/app.py`
- Modify: `clicky-py/clicky/ui/panel.py`

**Steps:**

- [ ] **Step 1:** Add `ResponseView` to panel layout below transcript view. Wire `manager.response_delta` → `response_view.append_delta`, `manager.response_complete` → `response_view.set_full`, state transitions → show/hide the view based on state (visible during RESPONDING).

- [ ] **Step 2:** In `app.py` `run()`, replace direct signal wiring with `CompanionManager` construction and wire:
  - `hotkey.pressed/released/cancelled` → `manager._on_hotkey_*`
  - `mic.audio_level` → `panel.set_audio_level`
  - `mic.pcm_chunk` → feeds into transcription stream (managed inside CompanionManager)
  - `transcription.interim_transcript` → `manager._on_interim_transcript` → `panel.transcript.set_interim`
  - `transcription.final_transcript` → `manager._on_final_transcript`
  - `manager.state_changed` → `panel.set_state` AND `tray.set_state`
  - `manager.response_delta` → `panel.response.append_delta`
  - `manager.error` → stderr (banner in Phase 6)

- [ ] **Step 3:** Manual verification:
  - Run `uv run python -m clicky`.
  - Open DaVinci Resolve (or any visually distinctive app).
  - Hold Ctrl+Alt, ask *"what am i looking at? give me a one-sentence summary"*, release.
  - Expected: waveform during hold, transcript appears on release, "processing" state briefly, then Claude's text response streams into the panel.
  - **Critical panel-exclusion check:** in Claude's response, verify it describes DaVinci (or whatever app you have open), NOT the ClickyWin panel itself. If Claude says "I see a dark panel labeled ClickyWin" or similar, the `hide_for_capture` step is not working — debug until the panel is excluded from the screenshot.
  - Optionally: add a temporary debug line in `companion_manager.py` that saves captured JPEGs to `%TEMP%\clicky-debug-*.jpg` and open them in an image viewer to visually confirm the panel is not in the frame. Remove the debug line before committing.
  - Follow up: hold Ctrl+Alt and ask *"and what's the first thing i should click?"* (testing memory). Expected: Claude answers in DaVinci context, proving conversation history works.
  - Ask a deliberately unrelated question *"what's the capital of france?"*. Expected: Claude answers directly without over-referencing the screenshot.

- [ ] **Step 4:** Commit:
  ```bash
  git add clicky-py/clicky/app.py clicky-py/clicky/ui/panel.py
  git commit -m "feat(clicky-py): wire phase 4 — voice, screen, claude streaming response"
  ```

**Phase 4 milestone reached:** core loop works silently (no audio response yet).

---

## Phase 5: ElevenLabs TTS + interrupt handling

**Milestone:** Claude's response plays aloud through the speakers. Pressing Ctrl+Alt mid-response cuts the audio cleanly and starts a new question.

---

### Task 5.1: `TTSClient` module [IMPL]

**Files:**
- Create: `clicky-py/clicky/clients/tts_client.py`

Reference: Swift `ElevenLabsTTSClient.swift`.

**Steps:**

- [ ] **Step 1:** Create `clicky-py/clicky/clients/tts_client.py`:
  - `TTSClient(QObject)` class.
  - Qt signals: `playback_started = Signal()`, `playback_finished = Signal()`, `error = Signal(str)`.
  - Holds a `QMediaPlayer` instance and a `QAudioOutput` (the audio output must be explicitly attached via `player.setAudioOutput(audio_out)` — without it, `QMediaPlayer` is silent on Windows).
  - **Critical lifetime rule:** keep the raw MP3 `bytes`, the `QByteArray`, AND the `QBuffer` as instance attributes (`self._current_bytes`, `self._current_bytearray`, `self._current_buffer`). If any of these are garbage-collected while playback is in progress, `QMediaPlayer` will hang or crash. Replace them atomically on each new `speak()` call.
  - `async speak(text: str) -> None`:
    1. POSTs `{"text": text}` to `f"{worker_url}/tts"` via `httpx.AsyncClient`, receives full MP3 bytes.
    2. Stores bytes on `self._current_bytes`. Creates `QByteArray(self._current_bytes)` on `self._current_bytearray`. Creates `QBuffer(self._current_bytearray, parent=self)` on `self._current_buffer`.
    3. **Opens the buffer in read-only mode:** `self._current_buffer.open(QIODevice.OpenModeFlag.ReadOnly)`. Without this call, `QMediaPlayer` cannot read from it.
    4. Calls `player.setSourceDevice(self._current_buffer)` and `player.play()`.
    5. Emits `playback_started`.
    6. Awaits the player's `mediaStatusChanged` signal for `EndOfMedia` via an `asyncio.Future` that the slot resolves; then emits `playback_finished`.
  - `stop()` method that calls `player.stop()` and resolves the future with a cancelled flag so the awaiter returns cleanly.
  - On any HTTP or playback error, emits `error(...)`.

- [ ] **Step 2:** Commit:
  ```bash
  git add clicky-py/clicky/clients/tts_client.py
  git commit -m "feat(clicky-py): add ElevenLabs TTS client with QMediaPlayer playback"
  ```

---

### Task 5.2: Wire TTS into CompanionManager and add interrupt handling [IMPL]

**Files:**
- Modify: `clicky-py/clicky/companion_manager.py`
- Modify: `clicky-py/clicky/app.py`

**Steps:**

- [ ] **Step 1:** In `companion_manager.py`:
  - Add `tts: TTSClient` to the constructor.
  - On `response_complete(full_text: str)`: call `asyncio.create_task(self._speak(full_text))`. `_speak` awaits `tts.speak(full_text)`. While speaking, state stays at RESPONDING. On completion (or error), state returns to IDLE.
  - On `_on_hotkey_pressed()`: call `tts.stop()` before starting new capture. This cuts in-flight audio immediately.
  - On `_on_hotkey_pressed()` also cancel `_current_task` (LLM stream) if not done.

- [ ] **Step 2:** In `app.py`:
  - Instantiate `TTSClient(worker_url=config.worker_url)`.
  - Pass it to `CompanionManager(...)`.

- [ ] **Step 3:** Manual verification:
  - Run `uv run python -m clicky`.
  - Ask Clicky a question. Expected: text streams in panel AND voice plays through speakers.
  - Mid-playback, press Ctrl+Alt again and speak a new question. Expected: audio stops immediately; new capture starts; response to new question plays.

- [ ] **Step 4:** Commit:
  ```bash
  git add clicky-py/clicky/companion_manager.py clicky-py/clicky/app.py
  git commit -m "feat(clicky-py): add TTS playback and interrupt handling"
  ```

**Phase 5 milestone reached:** full voice loop — the core ClickyWin experience is working.

---

## Phase 6: Polish — banners, logging, first-run, model picker, design system, icon states

**Milestone:** v1 UX is clean. Errors show clear red banners. First-run auto-opens panel. Model picker is in the panel. Design tokens are extracted. Tray icon changes color with state.

---

### Task 6.1: `StatusBanner` widget + error routing [IMPL]

**Files:**
- Create: `clicky-py/clicky/ui/status_banner.py`
- Modify: `clicky-py/clicky/ui/panel.py`
- Modify: `clicky-py/clicky/app.py`

**Steps:**

- [ ] **Step 1:** Create `status_banner.py` with a `StatusBanner(QWidget)` that supports three modes (info/warning/error), auto-hides after a next-success signal, and displays optional action button text and callback.

- [ ] **Step 2:** Add the banner to the panel layout at the top. Add methods `show_error(text, action_label=None, on_action=None)`, `show_warning(text, ...)`, `clear()`.

- [ ] **Step 3:** In `app.py`, replace `print(..., file=sys.stderr)` error handlers with banner calls. Connect `manager.error` → `panel.banner.show_error`. Connect `manager.success_turn_completed` → `panel.banner.clear` (this is a discrete "a full turn completed without error" signal emitted by `CompanionManager` — NOT a generic `state_changed == IDLE` transition, which also fires on errors and cancellations). This precise wiring satisfies PRD user story 30.

- [ ] **Step 4:** Manual verification: disconnect from wifi, ask a question, expect a red banner. Reconnect, ask again, banner clears.

- [ ] **Step 5:** Commit:
  ```bash
  git add clicky-py/clicky/ui/status_banner.py clicky-py/clicky/ui/panel.py clicky-py/clicky/app.py
  git commit -m "feat(clicky-py): add status banner for error/warning feedback"
  ```

---

### Task 6.2: `logging_config` module with rotating file handler [IMPL]

**Files:**
- Create: `clicky-py/clicky/logging_config.py`
- Modify: `clicky-py/clicky/app.py`

**Steps:**

- [ ] **Step 1:** Create `logging_config.py`:
  - `configure_logging(log_dir: Path, level: str) -> None`:
    - Create `log_dir` if missing.
    - Configure root logger with `RotatingFileHandler(log_dir / "clicky.log", maxBytes=5_000_000, backupCount=3)` and a `StreamHandler(sys.stderr)`.
    - Format: `%(asctime)s %(levelname)s %(name)s: %(message)s`.
    - Set level from the string.

- [ ] **Step 2:** In `app.py` `bootstrap()`, after loading config, call `configure_logging(result.log_dir, config.log_level)` (only if config loaded successfully; otherwise INFO default).

- [ ] **Step 3:** Replace print statements across modules with `logging.getLogger(__name__)` calls. Keep it light — don't blanket-rewrite, just the most useful sites (errors, state transitions, HTTP failures).

- [ ] **Step 4:** Manual verification: run the app, trigger a transcription, check `%APPDATA%\ClickyWin\logs\clicky.log` contains entries.

- [ ] **Step 5:** Commit:
  ```bash
  git add clicky-py/clicky/logging_config.py clicky-py/clicky/app.py clicky-py/clicky/companion_manager.py clicky-py/clicky/clients/
  git commit -m "feat(clicky-py): add rotating file logging"
  ```

---

### Task 6.3: First-run detection + config-invalid banner [IMPL]

**Files:**
- Modify: `clicky-py/clicky/app.py`
- Modify: `clicky-py/clicky/ui/panel.py`

**Steps:**

- [ ] **Step 1:** In `app.py` `run()`:
  - If `result.was_first_run` or `result.config_error is not None`, show panel immediately via `panel.show_near_tray(tray)`.
  - If `result.config_error`, call `panel.banner.show_warning(f"Invalid config at {result.config_path}: {result.config_error}", action_label="Open config", on_action=lambda: os.startfile(result.config_path))`. Disable PTT until config is fixed.
  - If `result.was_first_run` but config loaded successfully, show a transient info banner "Press Ctrl+Alt to talk. First run — edit your config at <path> if needed."

- [ ] **Step 2:** Manual verification:
  - Delete config, run. Expected: panel auto-opens, yellow banner, PTT disabled.
  - Fix config, re-run. Expected: panel auto-opens, info banner, PTT works.
  - Third run (not first run). Expected: panel stays hidden until clicked or hotkey pressed.

- [ ] **Step 3:** Commit:
  ```bash
  git add clicky-py/clicky/app.py clicky-py/clicky/ui/panel.py
  git commit -m "feat(clicky-py): first-run and config-error onboarding flow"
  ```

---

### Task 6.4: `ModelPicker` widget [IMPL]

**Files:**
- Create: `clicky-py/clicky/ui/model_picker.py`
- Modify: `clicky-py/clicky/ui/panel.py`
- Modify: `clicky-py/clicky/app.py`

**Steps:**

- [ ] **Step 1:** Create `model_picker.py`:
  - `ModelPicker(QWidget)` with a `QComboBox` containing "Sonnet 4.6" (`claude-sonnet-4-6`) and "Opus 4.6" (`claude-opus-4-6`).
  - Qt signal: `model_changed = Signal(str)`.
  - Method `set_model(model_id: str)` to set the initial selection without firing the signal.

- [ ] **Step 2:** Add it to the panel layout (above the quit button, visible always).

- [ ] **Step 3:** In `app.py`, initialize picker with `config.default_model`, connect `model_changed` → `manager.set_model`.

- [ ] **Step 4:** Manual verification: switch models via dropdown, ask a question, observe difference in response depth/speed.

- [ ] **Step 5:** Commit:
  ```bash
  git add clicky-py/clicky/ui/model_picker.py clicky-py/clicky/ui/panel.py clicky-py/clicky/app.py
  git commit -m "feat(clicky-py): add model picker (sonnet/opus) in panel"
  ```

---

### Task 6.5: `design_system` token module [IMPL]

**Files:**
- Create: `clicky-py/clicky/design_system.py`
- Modify: widgets to pull colors/radii from `DS.*`

Reference: Swift `DesignSystem.swift` (~880 lines). Port only the tokens our widgets actually use — don't blanket-copy.

**Steps:**

- [ ] **Step 1:** Create `design_system.py` with a `DS` class containing nested `Colors`, `CornerRadius`, `Spacing`, `Fonts` classes. Populate with values matching `leanring-buddy/DesignSystem.swift` for the tokens we reference (panel bg, accent blue, waveform color, text primary/secondary, error red, warning amber, success green, radii 16/12/8, spacing 8/12/16/24). Use `QColor` / `QFont` types.

- [ ] **Step 2:** Replace hardcoded color strings in `waveform_view.py`, `panel.py`, `status_banner.py`, `icon_factory.py`, `tray_icon.py` with `DS.Colors.*`.

- [ ] **Step 3:** Verify the app still renders correctly.

- [ ] **Step 4:** Commit:
  ```bash
  git add clicky-py/clicky/design_system.py clicky-py/clicky/ui clicky-py/clicky/icon_factory.py
  git commit -m "feat(clicky-py): extract design system tokens"
  ```

---

### Task 6.6: Tray icon state colors + permissions indicator [IMPL]

**Files:**
- Modify: `clicky-py/clicky/ui/tray_icon.py`
- Create: `clicky-py/clicky/ui/permissions_indicator.py`
- Modify: `clicky-py/clicky/ui/panel.py`
- Modify: `clicky-py/clicky/app.py`

**Steps:**

- [ ] **Step 1:** Ensure `TrayIcon.set_state(state)` re-renders the icon via `icon_factory` with color per `DS.Colors.accent_blue` (idle) / `accent_green` (listening) / `accent_amber` (responding) / `error_red` (error). Wire `manager.state_changed` → `tray.set_state`.

- [ ] **Step 2:** Create `permissions_indicator.py`:
  - Small `QWidget` with a colored dot + label ("mic ok" / "mic blocked").
  - Method `set_mic_status(ok: bool)`.

- [ ] **Step 3:** Add to panel layout (near bottom). Update status on mic error signal (set red + show "fix" button that opens `ms-settings:privacy-microphone` via `os.startfile`).

- [ ] **Step 4:** Manual verification: watch tray icon color change as you talk. Block mic in Windows settings, try to talk, observe red indicator + working "Open Settings" link.

- [ ] **Step 5:** Commit:
  ```bash
  git add clicky-py/clicky/ui clicky-py/clicky/app.py
  git commit -m "feat(clicky-py): tray icon state colors + permissions indicator"
  ```

---

## Phase 7: v1 build and ship

**Milestone:** A zipped `dist/clicky/` folder runs on a clean Windows machine with no Python installed.

---

### Task 7.1: POINT tag parser for v2 prep [TDD]

**Files:**
- Create: `clicky-py/clicky/point_parser.py`
- Create: `clicky-py/tests/test_point_parser.py`

Reference: Swift `CompanionManager.swift` lines 782–800 (`parsePointingCoordinates`).

**Steps:**

- [ ] **Step 1:** Write failing tests in `clicky-py/tests/test_point_parser.py` covering:
  - `[POINT:100,200:search bar]` on same screen — parsed, label captured
  - `[POINT:400,300:terminal:screen2]` on second screen — parsed, screen index captured
  - `[POINT:none]` — explicit no pointing, returns `None` tag, stripped from spoken text
  - Response with no POINT tag — returns full text unchanged and `None` coordinate
  - Label containing spaces (e.g. `[POINT:50,60:color grading panel]`) — full label captured
  - Trailing whitespace after the tag (e.g. `"text [POINT:1,2:x]   \n"`) — still parsed
  - **Negative: mid-response POINT** (e.g. `"click [POINT:1,2:x] then do X"`) — regex is anchored at end of string, so mid-response tag is NOT parsed and the full text is returned unchanged
  - **Negative: `[POINT:none]` with trailing non-whitespace** (e.g. `"[POINT:none] extra"`) — should fall through and return original text
  - **Edge: multiple POINT tags** (only the last end-anchored one is parsed)

- [ ] **Step 2:** Run tests. Expect fail.

- [ ] **Step 3:** Implement `clicky-py/clicky/point_parser.py`:
  - `@dataclass class PointTag(x: int, y: int, label: str, screen: int | None)`
  - `parse_point_tag(response: str) -> tuple[str, PointTag | None]` — returns `(spoken_text, tag)`. Port Farza's regex: `\[POINT:(?:none|(\d+)\s*,\s*(\d+)(?::([^\]:\s][^\]:]*?))?(?::screen(\d+))?)\]\s*$`.

- [ ] **Step 4:** Run tests. Expect pass.

- [ ] **Step 5:** Commit:
  ```bash
  git add clicky-py/clicky/point_parser.py clicky-py/tests/test_point_parser.py
  git commit -m "feat(clicky-py): add POINT tag parser (v2 overlay prep)"
  ```

---

### Task 7.2: PyInstaller spec and build [IMPL]

**Files:**
- Create: `clicky-py/clicky.spec`
- Create: `clicky-py/README.md`

**Steps:**

- [ ] **Step 1:** Create `clicky-py/clicky.spec`:
  - `Analysis` with `scripts=['clicky/__main__.py']`
  - Include `config.example.toml` as a data file
  - Include PySide6 plugins (platforms, imageformats, mediaservice) via `collect_data_files` and `collect_dynamic_libs` for PySide6
  - Hidden imports: `PySide6.QtMultimedia`, `sounddevice`, `pynput.keyboard._win32`, `mss.windows`
  - `EXE` with `name='ClickyWin'`, `console=False`
  - `COLLECT` produces `dist/clicky/` (onedir)

- [ ] **Step 2:** Run `uv run pyinstaller clicky.spec`. Fix any missing-module errors by adding hidden imports.

- [ ] **Step 3:** Run `dist/clicky/ClickyWin.exe` from Windows Explorer. Expected: tray icon appears, everything works just like `uv run python -m clicky`.

- [ ] **Step 4:** Zip `dist/clicky/` and test on a second machine if available (or at least a clean user account) — Python NOT installed.

- [ ] **Step 5:** Create `clicky-py/README.md` with these sections in order:
  - **What it is:** 2-sentence description positioning ClickyWin as a Windows port of Farza's Clicky, with a link to `https://github.com/farzaa/clicky`.
  - **Prerequisites:** Python 3.12, `uv`, Cloudflare account (free tier), API keys for Anthropic / AssemblyAI / ElevenLabs.
  - **One-paragraph Worker deploy guide:** explicit step-by-step on deploying the shared Cloudflare Worker — `cd ../worker && npm install && wrangler secret put ANTHROPIC_API_KEY && wrangler secret put ASSEMBLYAI_API_KEY && wrangler secret put ELEVENLABS_API_KEY && wrangler deploy`. Then copy the deployed URL into `%APPDATA%\ClickyWin\config.toml`. Satisfies PRD user story 6.
  - **Dev loop:** `uv sync && uv run python -m clicky`
  - **Build:** `uv run pyinstaller clicky.spec` → `dist/clicky/ClickyWin.exe`
  - **Tests + lint:** `uv run pytest` and `uv run ruff check .`
  - **Configuration:** reference to `config.example.toml` and what each field does.
  - **Troubleshooting:** mic permission, worker URL placeholder, SmartScreen warning on first run.
  - **Credits:** paragraph crediting Farza prominently with a link to the original repo.
  - **License notice:** MIT, references `clicky-py/LICENSE`.

- [ ] **Step 6:** Create `clicky-py/LICENSE` — MIT license text preserving Farza's copyright line from `LICENSE` at workspace root AND adding a new copyright line for the Python port. Format:
  ```
  MIT License

  Copyright (c) 2025 Farza Majeed (original Clicky for macOS)
  Copyright (c) 2026 <your name> (ClickyWin Python port)

  Permission is hereby granted, ...
  ```
  Satisfies PRD user story 40.

- [ ] **Step 7:** Commit:
  ```bash
  git add clicky-py/clicky.spec clicky-py/README.md clicky-py/LICENSE
  git commit -m "feat(clicky-py): add pyinstaller spec, readme, and license"
  ```

---

### Task 7.3: Full v1 smoke test and commit final milestone [IMPL]

**Files:** none — verification task.

**Steps:**

- [ ] **Step 1:** Fresh run through the full user journey:
  - Open DaVinci Resolve (or Blender, or Photoshop — anything visually distinctive).
  - Launch ClickyWin from `dist/clicky/ClickyWin.exe`.
  - Hold Ctrl+Alt and ask *"i just opened this, how do i start color grading?"*.
  - Verify: waveform shows, interim transcript appears, final transcript appears, response streams in panel, voice plays, full turn completes.
  - Follow up: *"which color wheel should i touch first?"* (tests memory).
  - Switch to Sonnet → ask a quick factual question, then switch to Opus → ask a deeper "explain how X works under the hood" question. Verify both models work.
  - Interrupt mid-response: press Ctrl+Alt while TTS is playing, ask a new question, verify clean cut-over.
  - Trigger an error: disable wifi, ask a question, verify red banner; re-enable wifi, ask again, verify banner clears and response works.

- [ ] **Step 2:** If all scenarios pass, tag the v1 commit:
  ```bash
  git tag -a clickywin-v1.0.0 -m "ClickyWin v1 — voice tutor for Windows learners"
  ```

- [ ] **Step 3:** Celebrate. The milestone is reached.

---

## Testing summary

At plan completion, test suite contents:

| Test file | Module tested | Test count target |
|---|---|---|
| `test_config.py` | `Config` TOML loader + validation + first-run | 6–8 |
| `test_conversation_history.py` | `ConversationHistory` | 4 |
| `test_llm_sse_parser.py` | Anthropic SSE parser incl. defensive unknown-block | 3 |
| `test_transcription_parser.py` | AssemblyAI v3 message parser | 5 |
| `test_screen_capture_labels.py` | `compose_screen_label` | 4 |
| `test_point_parser.py` | `parse_point_tag` (v2 prep) | 6 |
| **Total** | | **28–30 tests, sub-second runtime** |

Run with `uv run pytest` from `clicky-py/`. Run `uv run ruff check . && uv run ruff format --check .` before every commit.

---

## Skill references (@syntax)

- @superpowers:test-driven-development — mandatory for every task marked `[TDD]` above
- @superpowers:systematic-debugging — when any manual verification step fails unexpectedly
- @superpowers:verification-before-completion — before marking Phase 7 complete
- @superpowers:finishing-a-development-branch — when the full v1 is ready and you want to decide on integration/merge strategy for the eventual public repo cut

---

## Known risks / gotchas to watch for during implementation

1. **`qasync` + PySide6 version compatibility** — if qasync fails to bridge with PySide6 6.7, fall back to running the asyncio loop on a background thread and using `QTimer.singleShot(0, ...)` to marshal to the GUI thread. Note in a comment if you have to do this.
2. **`sounddevice` PCM buffer GC** — the numpy array passed to the callback is invalidated after the callback returns. Always copy (`.tobytes()`) before emitting the signal.
3. **AssemblyAI v3 URL shape** — the exact query parameters (`sample_rate`, `encoding`, `token`) may have changed since Farza's Swift code was written. Verify against AssemblyAI's current docs if the websocket handshake fails.
4. **PyInstaller missing modules** — `pynput` and `mss` have platform-specific submodules that PyInstaller sometimes misses. Add them to `hiddenimports` as compile errors surface.
5. **Per-monitor DPI call timing** — `SetProcessDpiAwareness(2)` must run BEFORE the `QApplication` is constructed. If it runs after, Qt will default to system-DPI mode and screenshots will be wrong on HiDPI displays.
6. **Panel positioning on multi-monitor setups** — `QSystemTrayIcon.geometry()` can return an empty rect on Windows before the icon is shown. Defer the first `show_near_tray` call until after `tray.show()`.
7. **Hotkey hook + Remote Desktop** — `SetWindowsHookEx(WH_KEYBOARD_LL)` doesn't fire inside RDP sessions in some configurations. Test in a local session.
8. **Rate limits from AssemblyAI** — the temp token is valid for 480s. If the user holds the app open for hours without talking, the first push-to-talk after a long idle may need a fresh token. Current implementation fetches a fresh token per press, which sidesteps this.
9. **pynput low-level hook conflicts** — some anti-cheat drivers (Vanguard, EasyAntiCheat, BattlEye) and kernel-level keyboard filter drivers block or interfere with `WH_KEYBOARD_LL` hooks. Test on a clean gaming-free machine first. If a user reports "hotkey doesn't fire," first ask what else is running in the background.
10. **`QSystemTrayIcon.geometry()` + DPI** — tray icon geometry can return pre-scaled or post-scaled coordinates inconsistently on multi-monitor DPI setups. When positioning the panel near the tray in `Panel.show_near_tray`, always clamp the final position to the containing monitor's work area via `QGuiApplication.screenAt(point).availableGeometry()`.
11. **ElevenLabs 429 rate-limit handling** — a rate-limited TTS call currently surfaces as a generic red banner with no retry. For v1 this is acceptable (you'd notice and back off). For v2 consider a single retry after 2 seconds plus a user-visible "TTS rate-limited, retrying" state.
12. **PyInstaller + antivirus false positives** — Windows Defender and some third-party AVs flag PyInstaller-built `.exe` files as suspicious because they extract a Python interpreter at runtime. Unsigned `--onedir` builds are less flagged than `--onefile` but still occasionally tripped. When handing off to a client, warn them about the SmartScreen "Unknown publisher" prompt.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-09-clickywin-v1.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for a ~45-task plan like this one because each task gets a clean context window.

2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Faster feedback loop but the session context grows as tasks accumulate.

Which approach?
