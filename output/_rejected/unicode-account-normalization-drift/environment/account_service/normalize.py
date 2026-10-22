"""Unicode normalization utilities for the account service.

Provides functions for normalizing usernames to consistent forms
for storage, lookup, and display.
"""
import unicodedata
from account_service.config import NORMALIZATION_FORM


def normalize_for_storage(username):
    """Normalizes usernames for consistent storage and lookup.

    Reads the configured normalization form from config.py and applies
    it to the input string. This is the primary function that should be
    called when usernames enter the system.

    Args:
        username: The raw username string to normalize.

    Returns:
        The normalized username string, or the input unchanged if empty.
    """
    if not username:
        return username
    return unicodedata.normalize(NORMALIZATION_FORM, username)


def normalize_for_display(username):
    """Normalizes usernames for display purposes.

    Uses NFC form which is the canonical storage form for this application.
    Display normalization ensures that visually identical characters are
    rendered consistently regardless of internal representation.

    Args:
        username: The username string to normalize for display.

    Returns:
        The NFC-normalized username string, or the input unchanged if empty.
    """
    if not username:
        return username
    return unicodedata.normalize('NFC', username)


def is_normalized(username, form=None):
    """Check if a username is already in the specified normalization form.

    Useful for validation and debugging to determine whether a string
    needs further normalization.

    Args:
        username: The string to check.
        form: The normalization form to check against. Defaults to the
              configured NORMALIZATION_FORM.

    Returns:
        True if the username is already in the specified form.
    """
    if not username:
        return True
    if form is None:
        form = NORMALIZATION_FORM
    return unicodedata.is_normalized(form, username)


def get_normalization_form():
    """Return the currently configured normalization form.

    Returns:
        The string identifier of the active normalization form
        (e.g., 'NFC', 'NFD', 'NFKC', 'NFKD').
    """
    return NORMALIZATION_FORM


def compare_normalized(username_a, username_b, form=None):
    """Compare two usernames after normalization.

    Two usernames that look identical on screen may have different
    internal representations. This function normalizes both and
    checks for equality.

    Args:
        username_a: First username to compare.
        username_b: Second username to compare.
        form: Normalization form to use. Defaults to configured form.

    Returns:
        True if both usernames are equal after normalization.
    """
    if form is None:
        form = NORMALIZATION_FORM
    a = unicodedata.normalize(form, username_a) if username_a else ''
    b = unicodedata.normalize(form, username_b) if username_b else ''
    return a == b


def detect_form(username):
    """Detect which normalization form a username is likely in.

    Checks NFC and NFD forms and returns a list of forms that
    the string matches.

    Args:
        username: The string to analyze.

    Returns:
        A list of normalization form strings that the username matches.
    """
    if not username:
        return ['NFC', 'NFD', 'NFKC', 'NFKD']
    forms = []
    for f in ['NFC', 'NFD', 'NFKC', 'NFKD']:
        if unicodedata.is_normalized(f, username):
            forms.append(f)
    return forms
