"""Authentication routes for the account service.

Handles user registration and login. The register endpoint creates
new accounts with cleaned and normalized usernames. The login endpoint
looks up accounts using normalized usernames.
"""
from flask import Blueprint, request, jsonify
from account_service.validation import clean_username, validate_username
from account_service.normalize import normalize_for_storage
from account_service.db import (
    get_account_by_username,
    create_account,
    add_balance_history,
)
from account_service.decorators import handle_errors

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
@handle_errors
def register():
    """Register a new account.

    Expects JSON body with 'username' (required) and 'balance' (optional).

    The username goes through the full cleaning pipeline:
    1. clean_username (sanitize + canonicalize)
    2. validate_username (format checks)

    Returns 201 with account info on success, 400 for validation errors,
    or 409 if the username already exists.

    Request JSON:
        username (str): The desired username
        balance (float, optional): Initial balance, default 0.0

    Response JSON:
        id (int): The new account ID
        username (str): The cleaned username
        balance (float): The initial balance
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    username = data.get('username', '')
    initial_balance = data.get('balance', 0.0)

    # Clean the username (includes normalization via _canonicalize)
    cleaned = clean_username(username)

    is_valid, error = validate_username(cleaned)
    if not is_valid:
        return jsonify({'error': error}), 400

    # Check for existing account
    existing = get_account_by_username(cleaned)
    if existing:
        return jsonify({'error': f"Username '{cleaned}' already exists"}), 409

    account_id = create_account(cleaned, initial_balance)
    if initial_balance > 0:
        add_balance_history(account_id, cleaned, 0.0, initial_balance, 'deposit')

    return jsonify({
        'id': account_id,
        'username': cleaned,
        'balance': initial_balance,
    }), 201


@auth_bp.route('/login', methods=['POST'])
@handle_errors
def login():
    """Login endpoint.

    Looks up an account by username after normalizing the input.
    Returns account information if the account exists.

    Request JSON:
        username (str): The username to look up

    Response JSON:
        id (int): The account ID
        username (str): The stored username
        balance (float): The current balance
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400

    username = data.get('username', '')

    # Normalize for lookup using the configured normalization form
    normalized = normalize_for_storage(username.strip().lower())

    account = get_account_by_username(normalized)
    if not account:
        return jsonify({'error': 'Invalid credentials'}), 401

    return jsonify({
        'id': account['id'],
        'username': account['username'],
        'balance': account['balance'],
    }), 200
