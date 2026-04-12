"""KB matching and section selection for ClickyWin v3."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class KBApp:
    """A loaded knowledge base for one application."""

    name: str
    window_titles: list[str]
    overview: str  # overview.md content
    sections: list[tuple[str, str]] = field(default_factory=list)  # (filename, content)


STOP_WORDS = frozenset(
    {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "i", "me", "my", "we",
        "you", "your", "it", "its", "this", "that", "how", "what", "where",
        "when", "why", "which", "who", "in", "on", "at", "to", "for", "of",
        "with", "by", "from", "and", "or", "not", "no", "but", "if", "so",
        "just", "about", "up", "out", "into",
    }
)


def match_app(window_title: str, apps: list[KBApp]) -> KBApp | None:
    """Case-insensitive substring match. First match wins."""
    if not window_title:
        return None
    title_lower = window_title.lower()
    for app in apps:
        for wt in app.window_titles:
            if wt.lower() in title_lower:
                return app
    return None


def _extract_keywords(text: str) -> set[str]:
    words = set(text.lower().split())
    return words - STOP_WORDS


def _extract_headings(content: str) -> str:
    return " ".join(
        line.lstrip("#").strip()
        for line in content.splitlines()
        if line.startswith("#")
    )


def _score_section(headings_text: str, keywords: set[str]) -> int:
    heading_words = set(headings_text.lower().split())
    return len(heading_words & keywords)


def select_content(
    app: KBApp, transcript: str, budget_chars: int = 60_000
) -> str:
    """Select KB content within a character budget.

    Always includes overview. If all sections fit, include all.
    If over budget, rank sections by keyword overlap with transcript.
    If no transcript keywords, return overview only when over budget.
    """
    parts = [app.overview]
    remaining = budget_chars - len(app.overview)

    if not app.sections:
        return "\n\n".join(parts)

    # Check if everything fits
    total_sections = sum(len(c) for _, c in app.sections)
    if total_sections <= remaining:
        for _, content in app.sections:
            parts.append(content)
        return "\n\n".join(parts)

    # Over budget -- rank by keyword overlap with transcript
    keywords = _extract_keywords(transcript)
    if not keywords:
        # No signal to rank -- return overview only
        return "\n\n".join(parts)

    scored = []
    for _filename, content in app.sections:
        headings = _extract_headings(content)
        score = _score_section(headings, keywords)
        scored.append((score, len(content), content))

    scored.sort(key=lambda t: (-t[0], t[1]))

    for _score, size, content in scored:
        if size <= remaining:
            parts.append(content)
            remaining -= size

    return "\n\n".join(parts)
