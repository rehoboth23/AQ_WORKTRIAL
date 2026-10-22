#!/usr/bin/env python3
"""Entry point for building the Petrify static site."""

import sys
from petrify.builder import SiteBuilder


def main():
    try:
        builder = SiteBuilder('site.yaml')
        builder.build()
    except Exception as e:
        print(f"Build failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
