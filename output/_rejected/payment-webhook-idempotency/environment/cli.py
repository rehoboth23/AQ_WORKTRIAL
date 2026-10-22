"""Command-line interface for the payment webhook consumer."""

import sys
import argparse
from webhook_consumer.db import get_connection, init_db
from webhook_consumer.receiver import WebhookReceiver
from webhook_consumer.processor import PaymentProcessor
from webhook_consumer.reconcile import Reconciler


def cmd_init(args):
    """Initialize the database schema."""
    conn = get_connection()
    init_db(conn)
    print("Database schema initialized.")
    conn.close()


def cmd_process(args):
    """Process all pending payment deliveries."""
    conn = get_connection()
    processor = PaymentProcessor(
        conn,
        crash_after_balance=args.crash_after_balance,
        crash_after_event=args.crash_after_event
    )
    processor.process_pending()
    conn.close()


def cmd_reconcile(args):
    """Reconcile account balances against expected values."""
    conn = get_connection()
    reconciler = Reconciler(conn)
    discrepancies = reconciler.reconcile()
    if discrepancies:
        for d in discrepancies:
            print(
                f"DISCREPANCY: {d['account_id']} ({d['name']}) - "
                f"balance={d['current_balance']:.2f}, "
                f"expected={d['expected_balance']:.2f}, "
                f"difference={d['difference']:+.2f}"
            )
    else:
        print("All accounts reconciled successfully.")
    conn.close()


def cmd_receive(args):
    """Receive a delivery notification from the payment provider."""
    conn = get_connection()
    receiver = WebhookReceiver(conn)
    result = receiver.receive_delivery(
        args.delivery_id, args.event_id, args.account_id, args.amount
    )
    print(f"Status: {result['status']}")
    if "delivery_id" in result:
        print(f"  delivery_id: {result['delivery_id']}")
    if "event_id" in result:
        print(f"  event_id: {result['event_id']}")
    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Payment webhook consumer for PayStream delivery notifications"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init
    subparsers.add_parser("init", help="Initialize the database schema")

    # process
    process_parser = subparsers.add_parser(
        "process", help="Process pending deliveries"
    )
    process_parser.add_argument(
        "--crash-after-balance", action="store_true",
        help=argparse.SUPPRESS
    )
    process_parser.add_argument(
        "--crash-after-event", action="store_true",
        help=argparse.SUPPRESS
    )

    # reconcile
    subparsers.add_parser("reconcile", help="Reconcile account balances")

    # receive
    receive_parser = subparsers.add_parser(
        "receive", help="Receive a delivery notification"
    )
    receive_parser.add_argument("delivery_id", help="Unique delivery identifier")
    receive_parser.add_argument(
        "event_id", help="Event identifier (shared across retries)"
    )
    receive_parser.add_argument("account_id", help="Target account identifier")
    receive_parser.add_argument("amount", type=float, help="Payment amount")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "process":
        cmd_process(args)
    elif args.command == "reconcile":
        cmd_reconcile(args)
    elif args.command == "receive":
        cmd_receive(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
