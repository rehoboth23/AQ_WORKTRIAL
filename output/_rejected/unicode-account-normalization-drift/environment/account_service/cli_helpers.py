"""Helper functions for the CLI.

These functions are used by the CLI commands to process user input
before it reaches the database layer. They provide a separate
cleaning pipeline from the web API's validation module, reflecting
the CLI's different input handling needs (e.g., command-line arguments
may not need the same Unicode processing as JSON body fields).
"""
from account_service.config import MAX_USERNAME_LENGTH


def clean_username(username):
    """Clean a username for CLI operations.

    Strips whitespace and converts to lowercase. This performs
    the basic input cleaning that is appropriate for command-line
    arguments which are already in a controlled environment.

    Args:
        username: The raw username string from command-line input.

    Returns:
        The cleaned username string, or empty string if input is falsy.
    """
    if not username:
        return ''
    return username.strip().lower()


def format_account(account):
    """Format an account dict for CLI display.

    Args:
        account: A dict with account fields.

    Returns:
        A formatted string suitable for terminal output.
    """
    if not account:
        return "Account not found"
    lines = [
        f"ID:       {account.get('id', 'N/A')}",
        f"Username: {account.get('username', 'N/A')}",
        f"Balance:  ${account.get('balance', 0.0):,.2f}",
        f"Created:  {account.get('created_at', 'N/A')}",
    ]
    return '\n'.join(lines)


def format_balance_history(history):
    """Format balance history entries for CLI display.

    Args:
        history: A list of dicts with balance history fields.

    Returns:
        A formatted string with one line per history entry.
    """
    if not history:
        return "No balance history"
    lines = []
    for entry in history:
        lines.append(
            f"  {entry.get('created_at', 'N/A')}: "
            f"{entry.get('operation', 'N/A'):12s} "
            f"${entry.get('old_balance', 0.0):>10,.2f} -> ${entry.get('new_balance', 0.0):>10,.2f}"
        )
    return '\n'.join(lines)


def validate_cli_username(username):
    """Validate a username for CLI input.

    Checks length and basic format requirements.

    Args:
        username: The cleaned username string.

    Returns:
        A tuple of (is_valid: bool, error_message: str or None).
    """
    if not username or not username.strip():
        return False, "Username cannot be empty"

    if len(username) > MAX_USERNAME_LENGTH:
        return False, f"Username exceeds maximum length of {MAX_USERNAME_LENGTH}"

    return True, None


def format_currency(amount):
    """Format a numeric amount as a currency string.

    Args:
        amount: The numeric value to format.

    Returns:
        A string like '$1,234.56'.
    """
    return f"${amount:,.2f}"


def parse_account_id(value):
    """Parse an account ID from a string.

    Args:
        value: The string to parse as an integer.

    Returns:
        The integer account ID, or None if parsing fails.
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
