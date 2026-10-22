"""Account balance routes for the account service.

Provides endpoints for checking balances, depositing funds, and
withdrawing funds. All username lookups use normalize_for_storage()
for consistent Unicode handling.
"""
from flask import Blueprint, request, jsonify
from account_service.normalize import normalize_for_storage
from account_service.validation import sanitize_username, validate_username
from account_service.db import (
    get_account_by_username,
    update_balance,
    add_balance_history,
)
from account_service.decorators import handle_errors
from account_service.exceptions import AccountNotFoundError, InsufficientBalanceError

accounts_bp = Blueprint('accounts', __name__)


@accounts_bp.route('/<username>/balance', methods=['GET'])
@handle_errors
def get_balance(username):
    """Get the balance for an account.

    URL Parameters:
        username (str): The account username

    Response JSON:
        username (str): The stored username
        balance (float): The current balance
    """
    normalized = normalize_for_storage(sanitize_username(username))

    account = get_account_by_username(normalized)
    if not account:
        raise AccountNotFoundError(f"Account '{username}' not found")

    return jsonify({'username': account['username'], 'balance': account['balance']}), 200


@accounts_bp.route('/<username>/deposit', methods=['POST'])
@handle_errors
def deposit(username):
    """Deposit funds into an account.

    URL Parameters:
        username (str): The account username

    Request JSON:
        amount (float): The amount to deposit (must be positive)

    Response JSON:
        username (str): The stored username
        old_balance (float): Balance before deposit
        new_balance (float): Balance after deposit
    """
    data = request.get_json()
    if not data or 'amount' not in data:
        return jsonify({'error': 'Amount required'}), 400

    try:
        amount = float(data['amount'])
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid amount'}), 400

    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400

    normalized = normalize_for_storage(sanitize_username(username))

    account = get_account_by_username(normalized)
    if not account:
        raise AccountNotFoundError(f"Account '{username}' not found")

    old_balance = account['balance']
    new_balance = old_balance + amount
    update_balance(account['id'], new_balance)
    add_balance_history(account['id'], account['username'], old_balance, new_balance, 'deposit')

    return jsonify({
        'username': account['username'],
        'old_balance': old_balance,
        'new_balance': new_balance,
    }), 200


@accounts_bp.route('/<username>/withdraw', methods=['POST'])
@handle_errors
def withdraw(username):
    """Withdraw funds from an account.

    URL Parameters:
        username (str): The account username

    Request JSON:
        amount (float): The amount to withdraw (must be positive)

    Response JSON:
        username (str): The stored username
        old_balance (float): Balance before withdrawal
        new_balance (float): Balance after withdrawal
    """
    data = request.get_json()
    if not data or 'amount' not in data:
        return jsonify({'error': 'Amount required'}), 400

    try:
        amount = float(data['amount'])
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid amount'}), 400

    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400

    normalized = normalize_for_storage(sanitize_username(username))

    account = get_account_by_username(normalized)
    if not account:
        raise AccountNotFoundError(f"Account '{username}' not found")

    old_balance = account['balance']
    if old_balance < amount:
        raise InsufficientBalanceError("Insufficient balance for withdrawal")

    new_balance = old_balance - amount
    update_balance(account['id'], new_balance)
    add_balance_history(account['id'], account['username'], old_balance, new_balance, 'withdrawal')

    return jsonify({
        'username': account['username'],
        'old_balance': old_balance,
        'new_balance': new_balance,
    }), 200


@accounts_bp.route('/<username>/history', methods=['GET'])
@handle_errors
def get_history(username):
    """Get balance history for an account.

    URL Parameters:
        username (str): The account username

    Response JSON:
        username (str): The stored username
        history (list): List of balance change entries
    """
    from account_service.db import get_balance_history

    normalized = normalize_for_storage(sanitize_username(username))

    account = get_account_by_username(normalized)
    if not account:
        raise AccountNotFoundError(f"Account '{username}' not found")

    history = get_balance_history(account['id'])
    return jsonify({
        'username': account['username'],
        'history': [
            {
                'old_balance': h['old_balance'],
                'new_balance': h['new_balance'],
                'operation': h['operation'],
                'created_at': h['created_at'],
            }
            for h in history
        ],
    }), 200
