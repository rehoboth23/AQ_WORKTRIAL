"""Import and export functionality for the account service.

Handles bulk operations on account data via CSV files. The import
function reads usernames and balances from a CSV, normalizes them,
and creates new accounts. The export function writes all accounts
to a CSV file.
"""
import csv
import os
from account_service.normalize import normalize_for_storage
from account_service.validation import sanitize_username, validate_username
from account_service.db import (
    get_account_by_username,
    create_account,
    update_balance,
    get_connection,
    add_balance_history,
)


def import_accounts(csv_path, default_balance=0.0):
    """Import accounts from a CSV file.

    Reads a CSV file with columns 'username' and optionally 'balance'.
    Each row is processed to create a new account or skip if the
    username already exists.

    The import pipeline:
    1. Read each row and extract username/balance
    2. Sanitize the username (strip + lowercase)
    3. Validate the username meets format requirements
    4. Check if an account with this username already exists
    5. Normalize the username for storage
    6. Create the account with the given balance

    Args:
        csv_path: Path to the CSV file to import.
        default_balance: Default balance if not specified in CSV.

    Returns:
        A dict with 'imported', 'skipped', and 'errors' counts.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
    """
    results = {'imported': 0, 'skipped': 0, 'errors': 0}

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row_num, row in enumerate(reader, start=1):
            username_raw = row.get('username', '').strip()

            if not username_raw:
                results['errors'] += 1
                continue

            try:
                balance = float(row.get('balance', default_balance))
            except (ValueError, TypeError):
                balance = default_balance

            # Sanitize the username (strip + lowercase only)
            username_clean = sanitize_username(username_raw)

            is_valid, error = validate_username(username_clean)
            if not is_valid:
                results['errors'] += 1
                continue

            # Check if account already exists using the raw cleaned username
            # This check happens before normalization, so accounts that exist
            # in a different Unicode form may not be detected as duplicates
            existing = get_account_by_username(username_clean)
            if existing:
                results['skipped'] += 1
                continue

            # Normalize for storage
            username_normalized = normalize_for_storage(username_clean)

            account_id = create_account(username_normalized, balance)
            add_balance_history(account_id, username_normalized, 0.0, balance, 'import')
            results['imported'] += 1

    return results


def export_accounts(csv_path):
    """Export all accounts to a CSV file.

    Writes all account data to a CSV file with columns:
    id, username, balance, created_at

    Args:
        csv_path: Path for the output CSV file.

    Returns:
        The number of accounts exported.
    """
    from account_service.db import get_all_accounts

    accounts = get_all_accounts()

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'username', 'balance', 'created_at'])
        for account in accounts:
            writer.writerow([
                account['id'],
                account['username'],
                account['balance'],
                account['created_at'],
            ])

    return len(accounts)


def validate_csv_format(csv_path):
    """Validate that a CSV file has the required columns and format.

    Checks that the file exists, is readable, and has at minimum
    a 'username' column.

    Args:
        csv_path: Path to the CSV file to validate.

    Returns:
        A tuple of (is_valid: bool, error_message: str or None).
    """
    if not os.path.exists(csv_path):
        return False, f"File not found: {csv_path}"

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return False, "CSV file has no headers"
            if 'username' not in reader.fieldnames:
                return False, "CSV must have a 'username' column"
    except Exception as e:
        return False, f"Error reading CSV: {str(e)}"

    return True, None


def preview_import(csv_path, max_rows=5):
    """Preview what an import would do without actually importing.

    Reads the CSV file and shows how many accounts would be
    imported, skipped, or errored.

    Args:
        csv_path: Path to the CSV file to preview.
        max_rows: Maximum number of rows to display.

    Returns:
        A dict with 'total_rows', 'preview_rows', and 'estimated_results'.
    """
    is_valid, error = validate_csv_format(csv_path)
    if not is_valid:
        return {'error': error}

    results = {'imported': 0, 'skipped': 0, 'errors': 0}
    preview_rows = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=1):
            username_raw = row.get('username', '').strip()
            if not username_raw:
                results['errors'] += 1
                continue

            username_clean = sanitize_username(username_raw)
            existing = get_account_by_username(username_clean)
            if existing:
                results['skipped'] += 1
            else:
                results['imported'] += 1

            if row_num <= max_rows:
                preview_rows.append({
                    'username': username_raw,
                    'cleaned': username_clean,
                    'status': 'skip' if existing else 'import',
                })

    return {
        'total_rows': sum(results.values()),
        'preview_rows': preview_rows,
        'estimated_results': results,
    }
