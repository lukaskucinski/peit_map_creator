"""
Popup formatting utilities for APPEIT Map Creator.

This module provides functions to format attribute values for display in map popups.
Handles special cases like URLs (converted to clickable links) and missing values.

Functions:
    format_popup_value: Format a single value for display in popup HTML
"""

from typing import Any


def format_popup_value(col: str, value: Any) -> str:
    """
    Format popup values, converting URLs to clickable hyperlinks.

    Detects URLs in column names or values and converts them to HTML links.
    Long URLs are truncated for better display. None/NaN values are handled gracefully.

    Parameters:
    -----------
    col : str
        Column name (used to detect URL fields)
    value : Any
        Value to format

    Returns:
    --------
    str
        Formatted HTML string safe for popup display

    Examples:
        >>> format_popup_value('name', 'Central Park')
        'Central Park'

        >>> format_popup_value('website', 'https://example.com/very/long/path')
        '<a href="..." target="_blank">https://example.com/very/long...</a>'

        >>> format_popup_value('count', None)
        'None'

        >>> format_popup_value('url', 'https://example.com')
        '<a href="https://example.com" target="_blank">https://example.com</a>'
    """
    # Handle None and NaN values
    if value is None or (isinstance(value, float) and value != value):  # NaN check
        return 'None'

    value_str = str(value)

    # Check if this is a URL field (by column name or value content)
    is_url = 'url' in col.lower() or value_str.startswith(('http://', 'https://'))

    if is_url:
        # Truncate long URLs for display
        if len(value_str) <= 60:
            display_text = value_str
        else:
            display_text = f"{value_str[:57]}..."

        return (
            f'<a href="{value_str}" target="_blank" '
            f'style="word-break: break-all; color: #0066cc;">{display_text}</a>'
        )

    return value_str
