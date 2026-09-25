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


def _build(args: argparse.Namespace) -> None:
    from barca import pipeline
    from barca.data import validate

    if not args.skip_interim:
        print("interim:", pipeline.build_interim())
    print("processed:", pipeline.build_processed())
    results = pipeline.validate_processed()
    print(validate.summary(results))
    if not validate.gate_passed(results):
        raise SystemExit("data-quality gate failed: see reports/data_quality.md")


def _features(args: argparse.Namespace) -> None:
    from barca.features import build

    print(build.build())


def _train(args: argparse.Namespace) -> None:
    import json

    from barca.models import production

    card = production.train(track=not args.no_mlflow)
    print(json.dumps(card["metrics"], indent=1))


def _explain(args: argparse.Namespace) -> None:
    from barca.xai import build

    if not args.global_only:
        print(build.build(max_evals=args.max_evals))
    print(build.build_global())


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

    build = sub.add_parser("build", help="interim -> processed -> validated")
    build.add_argument("--skip-interim", action="store_true", help="reuse existing interim tables")
    build.set_defaults(func=_build)

    features = sub.add_parser("features", help="build the feature store from validated data")
    features.set_defaults(func=_features)

    train = sub.add_parser("train", help="walk-forward training of the production outcome model")
    train.add_argument("--no-mlflow", action="store_true", help="skip experiment tracking")
    train.set_defaults(func=_train)

    explain = sub.add_parser("explain", help="precompute SHAP explanations, importances and PDP/ICE")
    explain.add_argument("--max-evals", type=int, default=400)
    explain.add_argument("--global-only", action="store_true")
    explain.set_defaults(func=_explain)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
