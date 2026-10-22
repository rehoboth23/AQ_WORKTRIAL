#!/usr/bin/env python3
"""
Address normaliser — currently a pass-through stub.

Your task: replace the normalise() function so it reproduces the
retired municipal normalisation engine on unseen addresses.

The engine applied about 25 ordered regex rewrite rules.
Study the training pairs in data/addresses.tsv and the postal
style guide in data/README.md.
"""
import argparse
import sys


def normalise(addr):
    """Normalise a single address.  Stub: returns input unchanged."""
    return addr


def main():
    parser = argparse.ArgumentParser(description='Normalise postal addresses')
    parser.add_argument('--input',  help='Input file (one address per line)')
    parser.add_argument('--output', help='Output file (one normalised address per line)')
    args = parser.parse_args()

    if args.input:
        with open(args.input, 'r') as f:
            lines = f.read().splitlines()
    else:
        lines = sys.stdin.read().splitlines()

    results = [normalise(line) for line in lines]

    output_text = '\n'.join(results)
    if output_text:
        output_text += '\n'

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output_text)
    else:
        sys.stdout.write(output_text)


if __name__ == '__main__':
    main()
