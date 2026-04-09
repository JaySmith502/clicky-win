"""Microphone capture via ``sounddevice`` — 16 kHz PCM16 mono, 100 ms chunks.

Opens a WASAPI input stream through PortAudio (via ``sounddevice``) and
emits raw little-endian int16 PCM bytes plus an RMS audio-level value on
every block. Consumers (e.g. the transcription uploader and the waveform
widget) connect to the Qt signals.

Audio config rationale
----------------------
Farza's Swift reference (``BuddyAudioConversionSupport.swift`` and
``BuddyDictationManager.swift``) does **not** hardcode a sample rate or a
chunk duration. Instead it installs an ``AVAudioEngine`` tap with
``bufferSize: 1024`` frames on the input node's native format, then runs
every buffer through ``BuddyPCM16AudioConverter`` which is initialized
with a ``targetSampleRate`` chosen by the active transcription provider.

ClickyWin's PRD § Question 6a + 6c pins the capture format directly to
**16 kHz PCM16 mono with 100 ms chunks** (``blocksize=1600``) to match
what the Deepgram streaming endpoint expects — this saves us from
building an AVAudioConverter-equivalent resampler on Windows. The values
here are therefore the PRD numbers, not Farza's (his are provider-driven).

Thread safety
-------------
sounddevice fires the stream callback on its own audio thread. Qt signal
emissions from that thread must be marshaled onto the thread this
``MicCapture`` QObject lives in (normally the main thread) via
``QMetaObject.invokeMethod`` with ``Qt.ConnectionType.QueuedConnection``.
This mirrors the pattern used in ``clicky/hotkey.py``; the difference is
that our signals carry payloads, so we use ``Q_ARG`` to pack the args.
"""

from __future__ import annotations

import math

import numpy as np
import sounddevice as sd
from PySide6.QtCore import (
    Q_ARG,
    QMetaObject,
    QObject,
    Qt,
    Signal,
    Slot,
)

# PRD § 6a/6c. Deepgram streaming linear16 accepts 16 kHz mono directly.
SAMPLE_RATE_HZ = 16000
CHANNELS = 1
# 100 ms at 16 kHz = 1600 frames per block.
BLOCK_SIZE_FRAMES = 1600
# int16 peak magnitude; |-32768| is the worst-case absolute value, which
# is what we divide by when normalizing RMS to [0, 1].
INT16_PEAK = 32768.0


class MicCapture(QObject):
    """Qt-friendly microphone capture backed by ``sounddevice``.

    Signals
    -------
    pcm_chunk(bytes)
        Raw little-endian int16 mono PCM for one 100 ms block. The bytes
        object is an independent copy of the audio thread's buffer — safe
        to hold onto, serialize, or forward to a network upload.
    audio_level(float)
        RMS of the block normalized into ``[0.0, 1.0]``. Intended for the
        waveform widget.
    error(str)
        User-visible error string. Emitted when the input stream cannot
        be opened or when an unexpected exception happens inside the
        audio callback.
    """

    pcm_chunk = Signal(bytes)
    audio_level = Signal(float)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._stream: sd.InputStream | None = None

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Open and start the input stream. Idempotent.

        On PortAudio failure (no default input device, privacy block,
        driver error) this emits ``error(...)`` and leaves the stream
        closed — callers should treat ``start()`` as best-effort and
        listen on ``error`` rather than catching exceptions.
        """
        if self._stream is not None:
            return

        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE_HZ,
                channels=CHANNELS,
                dtype="int16",
                blocksize=BLOCK_SIZE_FRAMES,
                callback=self._audio_callback,
            )
            stream.start()
        except sd.PortAudioError:
            self._post_error("microphone unavailable — check privacy settings")
            return
        except Exception as exc:  # noqa: BLE001 — surface any startup failure
            self._post_error(f"microphone unavailable: {exc}")
            return

        self._stream = stream

    def stop(self) -> None:
        """Stop and close the input stream. Idempotent."""
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        try:
            stream.stop()
        finally:
            stream.close()

    # ------------------------------------------------------------------
    # sounddevice callback (runs on PortAudio's audio thread)
    # ------------------------------------------------------------------
    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,  # noqa: ARG002 — required by sounddevice callback signature
        time_info,  # noqa: ANN001, ARG002 — CFFI struct, not type-friendly
        status: sd.CallbackFlags,  # noqa: ARG002 — overruns are non-fatal
    ) -> None:
        # sounddevice docs: "The memory of the input data is only valid
        # during the callback. If you want to keep the data for later,
        # you have to make a copy." indata.tobytes() copies into a fresh
        # bytes object, which is safe to hand off via a queued signal.
        try:
            data = indata.tobytes()
            # RMS in int16 space, normalized to [0, 1]. Clamp because a
            # peak sample of -32768 slightly exceeds INT16_PEAK after the
            # square-root / divide and we don't want the waveform widget
            # to receive values > 1.0.
            rms_raw = math.sqrt(float(np.mean(indata.astype(np.float32) ** 2)))
            level = min(rms_raw / INT16_PEAK, 1.0)
        except Exception as exc:  # noqa: BLE001 — callback must not raise
            self._post_error(f"audio capture error: {exc}")
            return

        QMetaObject.invokeMethod(
            self,
            "_emit_pcm_chunk",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(bytes, data),
        )
        QMetaObject.invokeMethod(
            self,
            "_emit_audio_level",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(float, level),
        )

    def _post_error(self, msg: str) -> None:
        QMetaObject.invokeMethod(
            self,
            "_emit_error",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, msg),
        )

    # ------------------------------------------------------------------
    # main-thread signal emitters
    # ------------------------------------------------------------------
    @Slot(bytes)
    def _emit_pcm_chunk(self, data: bytes) -> None:
        self.pcm_chunk.emit(data)

    @Slot(float)
    def _emit_audio_level(self, level: float) -> None:
        self.audio_level.emit(level)

    @Slot(str)
    def _emit_error(self, msg: str) -> None:
        self.error.emit(msg)
