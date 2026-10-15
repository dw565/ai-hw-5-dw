"""CLI: run the agent team on the open tickets.

    .venv/bin/python -m backend.run_tickets            # reset DB, run all open tickets
    .venv/bin/python -m backend.run_tickets --ticket 102 --no-reset
"""

import argparse
import asyncio
import json

from .team import run_tickets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ticket", type=int, action="append", help="ticket id (repeatable); default: all open")
    parser.add_argument("--no-reset", action="store_true", help="keep the current working DB instead of resetting")
    args = parser.parse_args()
    summary = asyncio.run(run_tickets(args.ticket, reset=not args.no_reset))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
