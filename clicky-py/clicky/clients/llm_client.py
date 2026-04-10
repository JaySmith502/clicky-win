"""Anthropic SSE stream parser for LLM text delta extraction.

This module provides a lightweight parser for Anthropic streaming API responses
delivered via Server-Sent Events (SSE). It will be extended in Task 4.5 with
the full LLMClient class for making streaming requests.
"""

from __future__ import annotations

import json
from typing import Iterator


def parse_anthropic_sse_stream(raw: bytes) -> Iterator[str]:
    """Parse an Anthropic SSE byte stream and yield text delta strings.

    Splits the raw bytes on double-newline SSE event boundaries, extracts
    ``event:`` and ``data:`` fields, and yields the ``text`` value from
    ``content_block_delta`` events whose delta type is ``text_delta``.

    Unknown ``content_block_start`` types are silently skipped — any subsequent
    ``content_block_delta`` events for that block are also skipped, preventing
    crashes when the API introduces new block types.

    Events ``message_start``, ``message_delta``, ``message_stop``,
    ``content_block_stop``, and ``ping`` are ignored.

    Args:
        raw: Raw SSE bytes from an Anthropic streaming response.

    Yields:
        Text fragments extracted from ``text_delta`` deltas.
    """
    if not raw:
        return

    text = raw.decode("utf-8", errors="replace")

    # Track per-index whether the block is a known text block.
    block_is_text: dict[int, bool] = {}

    # Split on blank lines to get individual SSE events.
    chunks = text.split("\n\n")

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        event_type: str | None = None
        data_line: str | None = None

        for line in chunk.splitlines():
            if line.startswith("event:"):
                event_type = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_line = line[len("data:"):].strip()

        if event_type is None or data_line is None:
            continue

        try:
            payload = json.loads(data_line)
        except json.JSONDecodeError:
            continue

        if event_type == "content_block_start":
            index: int = payload.get("index", 0)
            content_block = payload.get("content_block", {})
            block_type = content_block.get("type", "")
            block_is_text[index] = block_type == "text"

        elif event_type == "content_block_delta":
            index = payload.get("index", 0)
            # If block is unknown, skip silently.
            if not block_is_text.get(index, False):
                continue
            delta = payload.get("delta", {})
            if delta.get("type") == "text_delta":
                text_fragment = delta.get("text", "")
                if text_fragment:
                    yield text_fragment

        # All other event types (message_start, message_delta, message_stop,
        # content_block_stop, ping) are intentionally ignored.
