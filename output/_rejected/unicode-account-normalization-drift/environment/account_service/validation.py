"""Username validation and cleaning utilities.

Provides functions for sanitizing, validating, and cleaning usernames
before they are stored in the database. The cleaning pipeline consists
of several stages:

1. sanitize_username: Strip whitespace and lowercase
2. _canonicalize: Apply Unicode normalization (via _internal module)
3. clean_username: Combines sanitize + canonicalize

The validation functions check format requirements such as length
and character restrictions.
"""
import re
from account_service._internal import _canonicalize
from account_service.config import MAX_USERNAME_LENGTH, MIN_USERNAME_LENGTH


def sanitize_username(username):
    """Strip whitespace and lowercase the username.

    This performs basic sanitization: removing leading/trailing
    whitespace and converting to lowercase. It does not perform
    Unicode normalization — that is handled by _canonicalize().

    Args:
        username: The raw username string.

    Returns:
        The sanitized username, or empty string if input is falsy.
    """
    if not username:
        return ''
    return username.strip().lower()


def clean_username(username):
    """Fully clean and normalize a username for storage.

    Applies the complete cleaning pipeline:
    1. sanitize_username (strip + lowercase)
    2. _canonicalize (Unicode normalization)

    This should be used when a username first enters the system
    through user-facing entry points such as registration.

    Args:
        username: The raw username string.

    Returns:
        The cleaned and normalized username.
    """
    sanitized = sanitize_username(username)
    return _canonicalize(sanitized)


def validate_username(username):
    """Validate a username meets format requirements.

    Checks:
    - Not empty or whitespace-only
    - Does not exceed maximum length
    - Does not contain control characters
    - Does not contain prohibited patterns

    Args:
        username: The username string to validate (should already be
                 sanitized/lowercased).

    Returns:
        A tuple of (is_valid: bool, error_message: str or None).
    """
    if not username or not username.strip():
        return False, "Username cannot be empty or whitespace"

    if len(username) < MIN_USERNAME_LENGTH:
        return False, f"Username must be at least {MIN_USERNAME_LENGTH} character(s)"

    if len(username) > MAX_USERNAME_LENGTH:
        return False, f"Username exceeds maximum length of {MAX_USERNAME_LENGTH}"

    # Reject control characters
    if re.search(r'[\x00-\x1f\x7f]', username):
        return False, "Username contains control characters"

    # Reject usernames that are only punctuation or symbols
    if re.match(r'^[\W_]+$', username) and not any(c.isalpha() for c in username):
        return False, "Username must contain at least one letter or digit"

    return True, None


def validate_username_strict(username):
    """Validate a username with additional strictness checks.

    In addition to the basic validation, also checks for:
    - No consecutive special characters
    - No leading or trailing special characters (after whitespace removal)

    Args:
        username: The username string to validate.

    Returns:
        A tuple of (is_valid: bool, error_message: str or None).
    """
    is_valid, error = validate_username(username)
    if not is_valid:
        return is_valid, error

    # Check for consecutive non-alphanumeric characters
    if re.search(r'[^a-zA-Z0-9]{2,}', username):
        return False, "Username cannot contain consecutive special characters"

    return True, None


def is_ascii_only(username):
    """Check if a username contains only ASCII characters.

    Args:
        username: The username string to check.

    Returns:
        True if all characters are ASCII (code points 0-127).
    """
    if not username:
        return True
    try:
        username.encode('ascii')
        return True
    except UnicodeEncodeError:
        return False
