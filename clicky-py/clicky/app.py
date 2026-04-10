"""ClickyWin QApplication bootstrap.

Resolves the config file path via platformdirs, ensures the file exists
(creating from config.example.toml on first run), loads it, and holds
the resulting Config for downstream components to read.
"""

from __future__ import annotations

import asyncio
import sys
from collections import deque
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path

import qasync
from platformdirs import user_config_dir, user_log_dir
from PySide6.QtCore import QByteArray, QTimer
from PySide6.QtWidgets import QApplication

from clicky.clients.transcription_client import TranscriptionClient
from clicky.config import Config, ConfigError
from clicky.hotkey import HotkeyMonitor
from clicky.mic_capture import MicCapture
from clicky.state import VoiceState
from clicky.ui.panel import Panel
from clicky.ui.tray_icon import TrayIcon

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
    # config.example.toml sits next to the clicky package directory
    # (i.e. inside clicky-py/, alongside clicky/).
    return Path(__file__).resolve().parent.parent / "config.example.toml"


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


def run() -> int:
    """Start the ClickyWin tray app and run the Qt event loop.

    Wires together the tray icon, floating panel, global hotkey
    monitor, and transcription client. Blocks until the user quits
    via the tray menu.
    """
    result = bootstrap()

    if result.was_first_run:
        print(
            f"[clicky] first run: created config at {result.config_path}",
            file=sys.stderr,
        )

    if result.config_error is not None:
        # Phase 1: log to stderr and proceed. Phase 2+ will surface this
        # as a banner inside the panel.
        print(
            f"[clicky] config error: {result.config_error}",
            file=sys.stderr,
        )

    tray_icon = TrayIcon(initial_state=VoiceState.IDLE)
    panel = Panel()
    mic = MicCapture()

    mic.audio_level.connect(panel.set_audio_level)
    mic.error.connect(lambda msg: print(f"[clicky] mic error: {msg}", file=sys.stderr))

    def _toggle_panel() -> None:
        if panel.isVisible():
            panel.hide()
        else:
            panel.show_near_tray(tray_icon)

    tray_icon.toggle_panel_requested.connect(_toggle_panel)

    # ------------------------------------------------------------------
    # Transcription client (only when config loaded successfully)
    # ------------------------------------------------------------------
    transcription: TranscriptionClient | None = None
    if result.config is not None:
        transcription = TranscriptionClient(worker_url=result.config.worker_url)
        transcription.interim_transcript.connect(panel.transcript.set_interim)
        transcription.final_transcript.connect(panel.transcript.set_final)
        transcription.final_transcript.connect(
            lambda text: print(f"[clicky] final transcript: {text}", file=sys.stderr)
        )
        transcription.error.connect(
            lambda msg: print(f"[clicky] transcription error: {msg}", file=sys.stderr)
        )

    # ------------------------------------------------------------------
    # PCM deque bridge: mic.pcm_chunk → async generator for transcription
    # ------------------------------------------------------------------
    # Mutable state shared between the Qt signal handler (which appends
    # chunks) and the async generator (which drains them). Replaced on
    # every hotkey-press cycle so a stale generator from a previous
    # session cannot leak chunks into the new one.
    # PCM bridge state lives in a mutable container so that every closure
    # (_on_pcm_chunk, _pcm_async_generator, _on_hotkey_pressed,
    # _stop_transcription) always sees the *current* session's objects
    # without needing ``nonlocal`` rebinding (which only helps direct
    # assignments in the enclosing scope, not reads in sibling closures).
    _pcm: dict = {
        "deque": deque(),
        "event": asyncio.Event(),
        "done": False,
    }

    def _on_pcm_chunk(chunk: QByteArray) -> None:
        _pcm["deque"].append(chunk)
        _pcm["event"].set()

    mic.pcm_chunk.connect(_on_pcm_chunk)

    async def _pcm_async_generator() -> AsyncGenerator[QByteArray, None]:
        """Async generator that yields QByteArray chunks from the deque.

        Snapshots the deque and event at creation time so that a reset in
        ``_on_hotkey_pressed`` (which replaces the dict values) doesn't
        confuse a still-draining generator from the previous session.
        """
        dq = _pcm["deque"]
        ev = _pcm["event"]
        while True:
            await ev.wait()
            ev.clear()
            while dq:
                yield dq.popleft()
            if _pcm["done"]:
                return

    # Track the current transcription stream task so we can await it if
    # needed and avoid orphaned coroutines.
    _stream_task: list[asyncio.Task | None] = [None]

    # ------------------------------------------------------------------
    # Hotkey handlers
    # ------------------------------------------------------------------
    hotkey_binding = result.config.hotkey if result.config is not None else "ctrl+alt"
    hotkey_monitor = HotkeyMonitor(binding=hotkey_binding)

    def _on_hotkey_pressed() -> None:
        print("[clicky] hotkey pressed", file=sys.stderr)
        mic.start()
        panel.set_state(VoiceState.LISTENING)
        panel.show_near_tray(tray_icon)

        if transcription is not None:
            # Cancel any lingering stream task from a previous session
            # (rapid press-release-press can outrun stop_stream's
            # ensure_future).
            old = _stream_task[0]
            if old is not None and not old.done():
                old.cancel()
            # Reset the PCM bridge for a fresh session.
            _pcm["deque"] = deque()
            _pcm["event"] = asyncio.Event()
            _pcm["done"] = False
            panel.transcript.clear()
            _stream_task[0] = asyncio.ensure_future(
                transcription.start_stream(_pcm_async_generator())
            )

    def _stop_transcription() -> None:
        """Signal the PCM generator to terminate and stop the stream."""
        _pcm["done"] = True
        _pcm["event"].set()  # wake the generator so it sees the done flag
        if transcription is not None:
            asyncio.ensure_future(transcription.stop_stream())

    def _on_hotkey_released() -> None:
        print("[clicky] hotkey released", file=sys.stderr)
        mic.stop()
        _stop_transcription()
        panel.set_state(VoiceState.PROCESSING)

    def _on_hotkey_cancelled() -> None:
        print("[clicky] hotkey cancelled", file=sys.stderr)
        mic.stop()
        _stop_transcription()
        panel.set_state(VoiceState.IDLE)

    def _on_escape_pressed() -> None:
        # Only hide if the panel is visible — otherwise the Escape key
        # has nothing to act on.
        if panel.isVisible():
            panel.hide()

    hotkey_monitor.pressed.connect(_on_hotkey_pressed)
    hotkey_monitor.released.connect(_on_hotkey_released)
    hotkey_monitor.cancelled.connect(_on_hotkey_cancelled)
    hotkey_monitor.escape_pressed.connect(_on_escape_pressed)

    hotkey_monitor.start()
    tray_icon.show()

    # Ensure the pynput listener thread is stopped before the app exits,
    # otherwise Python may hang on interpreter shutdown waiting for it
    # (pynput's helper thread is not always daemonic on Windows).
    result.app.aboutToQuit.connect(hotkey_monitor.stop)
    result.app.aboutToQuit.connect(_stop_transcription)

    if result.was_first_run:
        # Delay the first-run auto-show so the tray icon has time to be
        # laid out — otherwise tray_icon.geometry() returns an empty rect
        # on Windows and the panel falls back to screen-centering.
        QTimer.singleShot(100, lambda: panel.show_near_tray(tray_icon))

    # Use qasync to bridge the Qt event loop with asyncio so that
    # asyncio.create_task / ensure_future work inside Qt signal handlers.
    loop = qasync.QEventLoop(result.app)
    asyncio.set_event_loop(loop)
    with loop:
        loop.run_forever()
    return 0
