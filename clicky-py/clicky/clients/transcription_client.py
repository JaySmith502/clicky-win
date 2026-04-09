"""AssemblyAI v3 streaming transcription message parser.

Pure parser for the AssemblyAI Universal-Streaming v3 websocket protocol. See
the Swift reference implementation at
`leanring-buddy/AssemblyAIStreamingTranscriptionProvider.swift` for the exact
message shapes this parser understands.

This module intentionally contains NO websocket, Qt, or async code. The
websocket lifecycle lives in a separate task (3.3).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptEvent:
    """A user-facing transcript update emitted by the parser.

    `is_final` is True when AssemblyAI has closed the turn (either via
    `end_of_turn` or `turn_is_formatted`), signalling the final text for that
    utterance. Interim events stream in as the user keeps speaking.
    """

    text: str
    is_final: bool


def parse_assemblyai_message(msg: dict) -> TranscriptEvent | None:
    """Parse a single AssemblyAI v3 websocket message.

    Returns a `TranscriptEvent` for user-facing transcript updates, or `None`
    for lifecycle/control messages (`Begin`, `Termination`, errors, unknown
    future types).

    The Swift reference lowercases the type before matching; we mirror that
    behaviour so any casing variants AssemblyAI sends still parse correctly.
    """
    message_type = msg.get("type")
    if not isinstance(message_type, str):
        return None

    if message_type.lower() != "turn":
        return None

    transcript = msg.get("transcript")
    if not isinstance(transcript, str):
        return None

    is_final = bool(msg.get("end_of_turn")) or bool(msg.get("turn_is_formatted"))
    return TranscriptEvent(text=transcript, is_final=is_final)
