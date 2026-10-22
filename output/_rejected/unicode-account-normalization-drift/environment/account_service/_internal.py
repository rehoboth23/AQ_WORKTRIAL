"""Internal normalization utilities.

This module provides low-level Unicode normalization functions used
by the validation module. It is not intended to be imported directly
by application code; use validation.clean_username() or
normalize.normalize_for_storage() instead.
"""
import unicodedata


def _canonicalize(username):
    """Apply canonical Unicode normalization to a username.

    This ensures that visually identical characters are represented
    consistently in their decomposed form for storage. The decomposition
    form is used because it preserves the logical structure of characters,
    making it easier to compare and transform usernames.

    Args:
        username: The username string to canonicalize.

    Returns:
        The canonicalized username string, or the input unchanged if empty.
    """
    if not username:
        return username
    return unicodedata.normalize('NFD', username)


def _decompose_char(char):
    """Decompose a single character into its component parts.

    Useful for debugging and inspecting how characters are represented
    internally.

    Args:
        char: A single character string.

    Returns:
        The decomposed form of the character.
    """
    return unicodedata.normalize('NFD', char)


def _compose_char(char):
    """Compose a single character from its decomposed parts.

    Args:
        char: A character string, possibly in decomposed form.

    Returns:
        The composed (NFC) form of the character.
    """
    return unicodedata.normalize('NFC', char)
