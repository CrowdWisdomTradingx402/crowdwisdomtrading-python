"""crowdwisdomtrading command line: quick checks and demos.

  crowdwisdomtrading catalog
  crowdwisdomtrading sample
  crowdwisdomtrading daily NVDA                   (free: daily crowd score)
  crowdwisdomtrading weekly NVDA                  (free: weekly crowd score)
  crowdwisdomtrading consensus NVDA [--as-of 2026-11-04] [--cycle daily]
  crowdwisdomtrading latest NVDA
  crowdwisdomtrading crowdmap NVDA
  crowdwisdomtrading history NVDA --from 2026-10-01 --to 2026-10-31
Pays with X402_WALLET_PRIVATE_KEY or uses CWT_API_KEY; --base overrides the API host.
"""
from __future__ import annotations

import argparse
import json
import sys

from crowdwisdomtrading.client import Client, CrowdWisdomError
from crowdwisdomtrading.payment import PaymentFailed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="crowdwisdomtrading", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["catalog", "sample", "daily", "weekly", "consensus", "latest", "today", "crowdmap", "history"])
    parser.add_argument("ticker", nargs="?")
    parser.add_argument("--as-of", dest="as_of")
    parser.add_argument("--cycle")
    parser.add_argument("--from", dest="date_from")
    parser.add_argument("--to", dest="date_to")
    parser.add_argument("--base")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args(argv)

    client = Client(args.base, cache=not args.no_cache)
    try:
        if args.command == "catalog":
            out = client.catalog()
        elif args.command == "sample":
            out = client.sample()
        elif args.command == "today":
            out = client.setups_today(args.cycle)
        else:
            if not args.ticker:
                parser.error("ticker required")
            if args.command == "daily":
                out = client.daily_sentiment(args.ticker)
            elif args.command == "weekly":
                out = client.weekly_sentiment(args.ticker)
            elif args.command == "consensus":
                out = client.consensus(args.ticker, as_of=args.as_of, cycle=args.cycle)
            elif args.command == "latest":
                out = client.setup_latest(args.ticker, cycle=args.cycle)
            elif args.command == "crowdmap":
                out = client.crowdmap(args.ticker)
            else:
                if not (args.date_from and args.date_to):
                    parser.error("--from and --to required")
                out = client.history(args.ticker, args.date_from, args.date_to, cycle=args.cycle)
    except PaymentFailed as exc:
        print(f"payment failed: {exc}", file=sys.stderr)
        return 2
    except CrowdWisdomError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
