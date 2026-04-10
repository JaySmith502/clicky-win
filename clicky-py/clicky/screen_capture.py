def compose_screen_label(
    screen_index: int, total_screens: int, is_cursor_screen: bool
) -> str:
    """Return a human-readable label for a captured screen.

    When there is only one screen the label is simplified. When multiple
    screens are present, each label includes a 1-based position and whether
    the cursor is currently on that screen.
    """
    if total_screens == 1:
        return "user's screen (cursor is here)"

    position = screen_index + 1
    if is_cursor_screen:
        return f"screen {position} of {total_screens} \u2014 cursor is on this screen (primary focus)"
    return f"screen {position} of {total_screens} \u2014 secondary screen"
