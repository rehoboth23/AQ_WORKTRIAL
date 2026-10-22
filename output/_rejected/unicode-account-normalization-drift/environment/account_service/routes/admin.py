"""Admin routes for the account service.

Provides endpoints for administrative operations such as
balance adjustments and account information lookups.

The adjust_balance endpoint supports both JSON and form-encoded
request bodies to accommodate different admin client tools.
"""
from flask import Blueprint, request, jsonify
from account_service.normalize import normalize_for_storage
from account_service.validation import sanitize_username
from account_service.db import (
    get_account_by_username,
    update_balance,
    add_balance_history,
    get_balance_history,
)
from account_service.decorators import handle_errors
from account_service.exceptions import AccountNotFoundError

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/adjust', methods=['POST'])
@handle_errors
def adjust_balance():
    """Adjust the balance of an account.

    Supports both JSON and form-encoded request bodies:
    - JSON: {"username": "...", "amount": 100.0}
    - Form: username=...&amount=...

    The amount can be positive (increase balance) or negative
    (decrease balance). This is intended for administrative
    corrections and overrides.

    Request JSON or Form:
        username (str): The account username
        amount (float): The adjustment amount (can be negative)

    Response JSON:
        username (str): The stored username
        old_balance (float): Balance before adjustment
        new_balance (float): Balance after adjustment
        adjustment (float): The applied amount
    """
    if request.is_json:
        # JSON body path
        data = request.get_json()
        username = data.get('username', '')
        try:
            amount = float(data.get('amount', 0))
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid amount'}), 400

        # JSON path properly normalizes the username
        normalized = normalize_for_storage(sanitize_username(username))
    else:
        # Form-encoded path
        username = request.form.get('username', '')
        try:
            amount = float(request.form.get('amount', 0))
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid amount'}), 400

        # Form-encoded path: strip and lowercase
        normalized = username.strip().lower()

    account = get_account_by_username(normalized)
    if not account:
        raise AccountNotFoundError(f"Account '{username}' not found")

    old_balance = account['balance']
    new_balance = old_balance + amount
    update_balance(account['id'], new_balance)
    add_balance_history(account['id'], account['username'], old_balance, new_balance, 'adjustment')

    return jsonify({
        'username': account['username'],
        'old_balance': old_balance,
        'new_balance': new_balance,
        'adjustment': amount,
    }), 200


@admin_bp.route('/account/<username>', methods=['GET'])
@handle_errors
def get_account_info(username):
    """Get detailed account information.

    URL Parameters:
        username (str): The account username

    Response JSON:
        id (int): Account ID
        username (str): Stored username
        balance (float): Current balance
        created_at (str): ISO 8601 creation timestamp
        history_count (int): Number of balance history entries
    """
    normalized = normalize_for_storage(sanitize_username(username))

    account = get_account_by_username(normalized)
    if not account:
        raise AccountNotFoundError(f"Account '{username}' not found")

    history = get_balance_history(account['id'])

    return jsonify({
        'id': account['id'],
        'username': account['username'],
        'balance': account['balance'],
        'created_at': account['created_at'],
        'history_count': len(history),
    }), 200


@admin_bp.route('/accounts', methods=['GET'])
@handle_errors
def list_accounts():
    """List all accounts with summary information.

    Query Parameters:
        min_balance (float, optional): Minimum balance filter
        max_balance (float, optional): Maximum balance filter

    Response JSON:
        accounts (list): List of account summaries
        total (int): Total number of matching accounts
    """
    from account_service.db import get_all_accounts

    min_bal = request.args.get('min_balance', type=float)
    max_bal = request.args.get('max_balance', type=float)

    accounts = get_all_accounts()

    if min_bal is not None:
        accounts = [a for a in accounts if a['balance'] >= min_bal]
    if max_bal is not None:
        accounts = [a for a in accounts if a['balance'] <= max_bal]

    return jsonify({
        'accounts': [
            {
                'id': a['id'],
                'username': a['username'],
                'balance': a['balance'],
                'created_at': a['created_at'],
            }
            for a in accounts
        ],
        'total': len(accounts),
    }), 200
