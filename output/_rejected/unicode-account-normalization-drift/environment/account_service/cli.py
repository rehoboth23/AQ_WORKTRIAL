"""CLI interface for the account service.

Provides command-line tools for account management, including
creating accounts, looking up balances, depositing/withdrawing
funds, and exporting data.

Usage:
    python3 -m account_service.cli <command> [options]
"""
import csv
import sys
import click
from account_service.cli_helpers import clean_username, format_account, format_balance_history
from account_service.normalize import normalize_for_storage
from account_service.validation import validate_username, sanitize_username
from account_service.db import (
    get_account_by_username,
    get_account_by_id,
    create_account,
    update_balance,
    add_balance_history,
    get_balance_history,
    get_all_accounts,
)
from account_service.exceptions import DuplicateUsernameError, AccountNotFoundError


@click.group()
def cli():
    """Account service command-line interface.

    Manage accounts, balances, and data exports from the terminal.
    """
    pass


@cli.command()
@click.argument('username')
@click.option('--balance', default=0.0, type=float, help='Initial balance')
def create(username, balance):
    """Create a new account.

    USERNAME is the account name to create.
    """
    cleaned = clean_username(username)

    is_valid, error = validate_username(cleaned)
    if not is_valid:
        click.echo(f"Error: {error}", err=True)
        sys.exit(1)

    existing = get_account_by_username(cleaned)
    if existing:
        click.echo(f"Error: Account '{cleaned}' already exists (ID: {existing['id']})", err=True)
        sys.exit(1)

    account_id = create_account(cleaned, balance)
    click.echo(f"Account created: ID={account_id}, username='{cleaned}', balance=${balance:,.2f}")


@cli.command()
@click.argument('username')
def lookup(username):
    """Look up an account by username.

    USERNAME is the account name to search for.
    """
    normalized = normalize_for_storage(sanitize_username(username))

    account = get_account_by_username(normalized)
    if not account:
        click.echo(f"Account '{username}' not found", err=True)
        sys.exit(1)

    click.echo(format_account(account))
    history = get_balance_history(account['id'])
    if history:
        click.echo("\nBalance History:")
        click.echo(format_balance_history(history))


@cli.command()
@click.argument('account_id', type=int)
@click.argument('amount', type=float)
def deposit(account_id, amount):
    """Deposit funds into an account.

    ACCOUNT_ID is the numeric account ID.
    AMOUNT is the amount to deposit (must be positive).
    """
    if amount <= 0:
        click.echo("Error: Amount must be positive", err=True)
        sys.exit(1)

    account = get_account_by_id(account_id)
    if not account:
        click.echo(f"Error: Account ID {account_id} not found", err=True)
        sys.exit(1)

    old_balance = account['balance']
    new_balance = old_balance + amount
    update_balance(account_id, new_balance)
    add_balance_history(account_id, account['username'], old_balance, new_balance, 'deposit')

    click.echo(f"Deposited ${amount:,.2f}. New balance: ${new_balance:,.2f}")


@cli.command()
@click.argument('account_id', type=int)
@click.argument('amount', type=float)
def withdraw(account_id, amount):
    """Withdraw funds from an account.

    ACCOUNT_ID is the numeric account ID.
    AMOUNT is the amount to withdraw (must be positive).
    """
    if amount <= 0:
        click.echo("Error: Amount must be positive", err=True)
        sys.exit(1)

    account = get_account_by_id(account_id)
    if not account:
        click.echo(f"Error: Account ID {account_id} not found", err=True)
        sys.exit(1)

    old_balance = account['balance']
    if old_balance < amount:
        click.echo("Error: Insufficient balance", err=True)
        sys.exit(1)

    new_balance = old_balance - amount
    update_balance(account_id, new_balance)
    add_balance_history(account_id, account['username'], old_balance, new_balance, 'withdrawal')

    click.echo(f"Withdrew ${amount:,.2f}. New balance: ${new_balance:,.2f}")


@cli.command()
@click.argument('output_path')
def export(output_path):
    """Export all accounts to a CSV file.

    OUTPUT_PATH is the file path for the CSV output.

    The CSV contains columns: id, username, balance, created_at
    """
    accounts = get_all_accounts()

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'username', 'balance', 'created_at'])
        for account in accounts:
            writer.writerow([
                account['id'],
                account['username'],
                account['balance'],
                account['created_at'],
            ])

    click.echo(f"Exported {len(accounts)} accounts to {output_path}")


@cli.command('list')
def list_accounts():
    """List all accounts.

    Displays a table of all accounts with their IDs, usernames,
    balances, and creation dates.
    """
    accounts = get_all_accounts()
    if not accounts:
        click.echo("No accounts found")
        return

    click.echo(f"{'ID':<6} {'Username':<25} {'Balance':>12} {'Created':<20}")
    click.echo('-' * 65)
    for account in accounts:
        click.echo(
            f"{account['id']:<6} {account['username']:<25} "
            f"${account['balance']:>10,.2f} {account['created_at']:<20}"
        )


@cli.command()
@click.argument('account_id', type=int)
def history(account_id):
    """Show balance history for an account.

    ACCOUNT_ID is the numeric account ID.
    """
    account = get_account_by_id(account_id)
    if not account:
        click.echo(f"Error: Account ID {account_id} not found", err=True)
        sys.exit(1)

    hist = get_balance_history(account_id)
    if not hist:
        click.echo("No balance history for this account")
        return

    click.echo(f"Balance history for {account['username']} (ID: {account_id}):")
    click.echo(format_balance_history(hist))


if __name__ == '__main__':
    cli()
