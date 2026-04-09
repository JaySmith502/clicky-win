"""Global hotkey monitor — strict modifier-only press/release detection.

Watches the keyboard via ``pynput`` on a background thread and emits
Qt signals when a configured modifier combination transitions between
pressed and released. The signals are marshaled to the main thread via
``QTimer.singleShot`` so downstream Qt slots can touch widgets safely.

Supported bindings (closed set in v1):

- ``"ctrl+alt"``: armed when (left or right Ctrl) **and** Alt are held
  **and nothing else** (no Shift, no Win, no letters) is held.
- ``"right_ctrl"``: armed when **only** right Ctrl is held — no other
  modifier, no regular key.

State machine (identical for both bindings)::

    UNARMED --(arming condition met on key press)--> ARMED     [emit pressed]
    ARMED   --(any non-required key pressed)------> CANCELLED  [emit cancelled]
    ARMED   --(any required modifier released)----> UNARMED    [emit released]
    CANCELLED --(all modifiers released)----------> UNARMED

After ``CANCELLED`` the monitor does **not** emit ``released`` — the
press was never a legitimate hotkey press from the user's perspective.
Once every key is lifted we silently return to ``UNARMED`` so the next
real Ctrl+Alt chord can fire again.

Note on deviation from Farza's Swift reference
-----------------------------------------------
``leanring-buddy/GlobalPushToTalkShortcutMonitor.swift`` (via
``BuddyPushToTalkShortcut.shortcutTransition``) uses a looser rule: it
emits ``.pressed`` whenever the device-independent modifier flag set
*contains* ``[.control, .option]`` and ``.released`` the moment that is
no longer true. It does **not** cancel when a third modifier (Shift) or
a regular key is additionally held, and it does not distinguish left
from right modifiers. ClickyWin's PRD § Question 5c explicitly tightens
this to strict modifier-only with cancel-on-other-key so that typing
Ctrl+Alt+T (a Windows shortcut) does not accidentally open a voice
session. We intentionally deviate from Farza here.
"""

from __future__ import annotations

from enum import Enum, auto

from pynput import keyboard
from PySide6.QtCore import QObject, QTimer, Signal


class _HotkeyState(Enum):
    UNARMED = auto()
    ARMED = auto()
    CANCELLED = auto()


def _normalize_key(key: keyboard.Key | keyboard.KeyCode | None) -> str | None:
    """Map a pynput key object to a stable string identifier.

    Returns ``None`` if the key cannot be identified (e.g. a dead key
    event with no char on some layouts).
    """
    if key is None:
        return None

    if isinstance(key, keyboard.Key):
        if key == keyboard.Key.ctrl_l:
            return "ctrl_l"
        if key == keyboard.Key.ctrl_r:
            return "ctrl_r"
        if key in (keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
            # alt_gr on international layouts is synthesised as Ctrl+Alt
            # by Windows; pynput still reports it as alt_gr. Map to
            # "alt" so Ctrl+AltGr behaves like Ctrl+Alt. Users on intl
            # layouts who hit false positives should switch to the
            # right_ctrl binding (see config.example.toml).
            return "alt"
        if key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
            return "shift"
        # pynput uses Key.cmd for Windows key on Windows; also expose
        # cmd_l / cmd_r for completeness in case of platform drift.
        if key == keyboard.Key.cmd:
            return "win"
        cmd_l = getattr(keyboard.Key, "cmd_l", None)
        cmd_r = getattr(keyboard.Key, "cmd_r", None)
        if cmd_l is not None and key == cmd_l:
            return "win"
        if cmd_r is not None and key == cmd_r:
            return "win"
        return str(key)

    # keyboard.KeyCode — regular character keys.
    char = getattr(key, "char", None)
    if char:
        return char
    return str(key)


class HotkeyMonitor(QObject):
    """Qt-friendly global hotkey monitor backed by pynput.

    Signals
    -------
    pressed
        The configured chord just became fully armed.
    released
        A previously armed chord ended because a required modifier was
        released.
    cancelled
        A previously armed chord was invalidated because the user
        pressed an additional key. ``released`` is **not** emitted in
        this case.
    """

    pressed = Signal()
    released = Signal()
    cancelled = Signal()

    _VALID_BINDINGS: frozenset[str] = frozenset({"ctrl+alt", "right_ctrl"})

    def __init__(self, binding: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        if binding not in self._VALID_BINDINGS:
            raise ValueError(
                f"Unknown hotkey binding {binding!r}; "
                f"expected one of {sorted(self._VALID_BINDINGS)}"
            )
        self._binding = binding
        self._held: set[str] = set()
        self._state: _HotkeyState = _HotkeyState.UNARMED
        self._listener: keyboard.Listener | None = None

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Install the global keyboard hook. Idempotent."""
        if self._listener is not None:
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._listener.start()

    def stop(self) -> None:
        """Remove the global keyboard hook and reset internal state."""
        listener = self._listener
        self._listener = None
        if listener is not None:
            listener.stop()
        self._held.clear()
        self._state = _HotkeyState.UNARMED

    # ------------------------------------------------------------------
    # pynput callbacks (run on the listener's background thread)
    # ------------------------------------------------------------------
    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        name = _normalize_key(key)
        if name is None:
            return
        # pynput fires on_press repeatedly while a key is held. Only
        # the first press (set insertion) matters for the state machine.
        already_held = name in self._held
        self._held.add(name)
        if already_held:
            return

        if self._state == _HotkeyState.UNARMED:
            if self._is_armed():
                self._state = _HotkeyState.ARMED
                self._emit(self.pressed)
            return

        if self._state == _HotkeyState.ARMED:
            # Any new key press while armed that breaks the strict
            # modifier-only condition cancels. _is_armed() re-checks
            # both "required mods present" and "nothing else held".
            if not self._is_armed():
                self._state = _HotkeyState.CANCELLED
                self._emit(self.cancelled)
            return

        # CANCELLED — absorb further presses until everything is lifted.

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        name = _normalize_key(key)
        if name is None:
            return
        self._held.discard(name)

        if self._state == _HotkeyState.ARMED:
            # Releasing any of the required modifiers ends the press.
            if not self._required_mods_all_held():
                self._state = _HotkeyState.UNARMED
                self._emit(self.released)
            return

        if self._state == _HotkeyState.CANCELLED:
            # Wait until every key is lifted before re-arming is
            # allowed. This prevents a partial release from sliding
            # straight back into ARMED without the user intending a
            # new press.
            if not self._held:
                self._state = _HotkeyState.UNARMED
            return

    # ------------------------------------------------------------------
    # arming predicates
    # ------------------------------------------------------------------
    def _required_mods_all_held(self) -> bool:
        if self._binding == "ctrl+alt":
            has_ctrl = "ctrl_l" in self._held or "ctrl_r" in self._held
            return has_ctrl and "alt" in self._held
        # right_ctrl
        return "ctrl_r" in self._held

    def _is_armed(self) -> bool:
        """True iff the currently-held set matches the binding exactly.

        "Exactly" means: all required modifiers are held AND no other
        key (modifier or regular) is held.
        """
        if not self._required_mods_all_held():
            return False

        if self._binding == "ctrl+alt":
            allowed: set[str] = {"alt"}
            # Accept either or both Ctrl variants; disallow everything else.
            if "ctrl_l" in self._held:
                allowed.add("ctrl_l")
            if "ctrl_r" in self._held:
                allowed.add("ctrl_r")
            return self._held <= allowed and self._held.issuperset({"alt"})

        # right_ctrl: held set must be exactly {"ctrl_r"}.
        return self._held == {"ctrl_r"}

    # ------------------------------------------------------------------
    # thread-safe signal emission
    # ------------------------------------------------------------------
    @staticmethod
    def _emit(signal: Signal) -> None:
        # pynput callbacks run on a background thread; hop onto the
        # main Qt thread via the event loop before firing the signal.
        QTimer.singleShot(0, signal.emit)
