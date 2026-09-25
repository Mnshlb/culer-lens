"""Command-line entry point: ``barca <command>``."""

from __future__ import annotations

import argparse
import logging
import sys


def _fetch(args: argparse.Namespace) -> None:
    from barca.data import load

    counts = load.fetch_statsbomb(include_360=args.with_360, sample=args.sample)
    print("statsbomb:", counts)
    print("football-data files fetched:", load.fetch_football_data())
    print("manifest:", load.write_manifest())


def _interim(args: argparse.Namespace) -> None:
    from barca import pipeline

    print(pipeline.build_interim())


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(prog="barca")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="download raw StatsBomb and football-data files")
    fetch.add_argument("--sample", type=int, default=None, help="only the N latest Barcelona matches")
    fetch.add_argument("--with-360", action="store_true", help="also download 360 freeze frames")
    fetch.set_defaults(func=_fetch)

    interim = sub.add_parser("interim", help="flatten raw JSON/CSV into interim Parquet")
    interim.set_defaults(func=_interim)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
