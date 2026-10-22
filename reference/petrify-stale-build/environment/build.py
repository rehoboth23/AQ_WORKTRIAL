#!/usr/bin/env python3
"""Build the site into dist/.

    python3 build.py           incremental build
    python3 build.py --clean   delete dist/ first, then build everything
"""

import argparse
import sys

from petrify.builder import SiteBuilder


def main():
    parser = argparse.ArgumentParser(description="Build the Petrify site.")
    parser.add_argument("--clean", action="store_true", help="delete the output directory first")
    parser.add_argument("--config", default="site.yaml")
    args = parser.parse_args()
    try:
        SiteBuilder(args.config).build(clean=args.clean)
    except Exception as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
