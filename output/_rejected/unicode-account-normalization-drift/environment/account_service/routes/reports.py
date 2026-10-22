"""Report routes for the account service.

Provides endpoints for generating summary reports about
account activity and balances.
"""
from datetime import datetime, timezone
from flask import Blueprint, jsonify
from account_service.db import get_connection, get_all_accounts
from account_service.decorators import handle_errors

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/monthly', methods=['GET'])
@handle_errors
def monthly_report():
    """Generate a monthly summary report.

    Returns account count, total balance, and recent activity summary.

    Response JSON:
        generated_at (str): ISO 8601 timestamp of report generation
        total_accounts (int): Number of accounts
        active_accounts (int): Accounts with positive balance
        negative_accounts (int): Accounts with negative balance
        total_balance (float): Sum of all balances
        recent_activity_count (int): Balance changes in last 30 days
    """
    accounts = get_all_accounts()

    total_balance = sum(a['balance'] for a in accounts)
    active_accounts = sum(1 for a in accounts if a['balance'] > 0)
    zero_accounts = sum(1 for a in accounts if a['balance'] == 0)
    negative_accounts = sum(1 for a in accounts if a['balance'] < 0)

    # Get recent activity count
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM balance_history WHERE created_at >= datetime('now', '-30 days')"
        ).fetchone()
        recent_activity = row['cnt'] if row else 0
    finally:
        conn.close()

    return jsonify({
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'total_accounts': len(accounts),
        'active_accounts': active_accounts,
        'zero_accounts': zero_accounts,
        'negative_accounts': negative_accounts,
        'total_balance': total_balance,
        'recent_activity_count': recent_activity,
    }), 200


@reports_bp.route('/summary', methods=['GET'])
@handle_errors
def balance_summary():
    """Get a balance distribution summary.

    Response JSON:
        min_balance (float): Minimum account balance
        max_balance (float): Maximum account balance
        avg_balance (float): Average account balance
        median_balance (float): Median account balance
    """
    accounts = get_all_accounts()

    if not accounts:
        return jsonify({
            'min_balance': 0,
            'max_balance': 0,
            'avg_balance': 0,
            'median_balance': 0,
        }), 200

    balances = sorted([a['balance'] for a in accounts])
    n = len(balances)
    median = balances[n // 2] if n % 2 == 1 else (balances[n // 2 - 1] + balances[n // 2]) / 2

    return jsonify({
        'min_balance': min(balances),
        'max_balance': max(balances),
        'avg_balance': sum(balances) / n,
        'median_balance': median,
    }), 200
