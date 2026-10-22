"""Allow running the package directly: python3 -m account_service"""
import sys

from account_service.cli import cli

if __name__ == "__main__":
    cli()
else:
    # When invoked as `python3 -m account_service`, __name__ is "__main__"
    # but if imported, just expose cli
    pass
