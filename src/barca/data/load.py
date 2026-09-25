"""Download raw data and read it back.

Raw files are written once and never modified afterwards. StatsBomb JSON is
stored gzip-compressed (lossless, roughly 10x smaller on disk); football-data
CSVs are stored exactly as served. Every file is listed in a manifest together
with its SHA-256 so later stages can prove which inputs they were built from.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from barca import config
from barca.data import sources

log = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(60.0, connect=15.0)
_RETRIES = 5


def _get(client: httpx.Client, url: str) -> bytes:
    delay = 1.0
    for attempt in range(1, _RETRIES + 1):
        try:
            response = client.get(url, follow_redirects=True)
            if response.status_code == 200:
                return response.content
            if response.status_code == 404:
                raise FileNotFoundError(url)
            log.warning("GET %s -> %s (attempt %d)", url, response.status_code, attempt)
        except httpx.TransportError as exc:
            log.warning("GET %s failed: %s (attempt %d)", url, exc, attempt)
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(f"giving up on {url} after {_RETRIES} attempts")


def _write_gz(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    with gzip.open(tmp, "wb", compresslevel=6) as fh:
        fh.write(payload)
    tmp.rename(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


# StatsBomb --------------------------------------------------------------------------


def statsbomb_path(kind: str, key: str | int) -> Path:
    return config.RAW_STATSBOMB / kind / f"{key}.json.gz"


def _fetch_statsbomb_file(client: httpx.Client, kind: str, key: str | int) -> Path:
    target = statsbomb_path(kind, key)
    if target.exists():
        return target
    remote_key = str(key).replace("_", "/") if kind == "matches" else key
    payload = _get(client, f"{sources.STATSBOMB_BASE_URL}/{kind}/{remote_key}.json")
    json.loads(payload)  # refuse to store a truncated or non-JSON body
    _write_gz(target, payload)
    return target


def load_competitions() -> list[dict[str, Any]]:
    return read_json(config.RAW_STATSBOMB / "competitions.json.gz")


def load_matches(competition_id: int, season_id: int) -> list[dict[str, Any]]:
    return read_json(statsbomb_path("matches", f"{competition_id}_{season_id}"))


def load_events(match_id: int) -> list[dict[str, Any]]:
    return read_json(statsbomb_path("events", match_id))


def load_lineups(match_id: int) -> list[dict[str, Any]]:
    return read_json(statsbomb_path("lineups", match_id))


def catalogue_seasons() -> list[dict[str, Any]]:
    """Competition-seasons in the competitions we care about."""
    return [c for c in load_competitions() if c["competition_id"] in sources.CATALOGUE_COMPETITIONS]


def is_in_scope(match: dict[str, Any]) -> bool:
    """Matches whose events and lineups the project downloads.

    All La Liga matches in the Barcelona era (including every match of the fully
    released 2015/16 season) plus any other Barcelona match from the same era,
    which in practice means the Champions League finals of 2009, 2011 and 2015.
    """
    season = match["season"]["season_name"]
    if not sources.in_scope_season(season):
        return False
    if match["competition"]["competition_id"] == sources.LA_LIGA:
        return True
    teams = {match["home_team"]["home_team_name"], match["away_team"]["away_team_name"]}
    return sources.BARCELONA in teams


def in_scope_matches() -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for season in catalogue_seasons():
        for match in load_matches(season["competition_id"], season["season_id"]):
            if is_in_scope(match):
                matches.append(match)
    return sorted(matches, key=lambda m: (m["match_date"], m["match_id"]))


def fetch_statsbomb(
    *,
    include_360: bool = False,
    sample: int | None = None,
    workers: int = 16,
) -> dict[str, int]:
    """Download the catalogue, then lineups and events for every in-scope match.

    ``sample`` limits the download to the N most recent Barcelona matches, which
    is what CI uses for the data-quality suite.
    """
    config.ensure_dirs()
    with httpx.Client(timeout=_TIMEOUT, http2=False) as client:
        comp_path = config.RAW_STATSBOMB / "competitions.json.gz"
        if not comp_path.exists():
            payload = _get(client, f"{sources.STATSBOMB_BASE_URL}/competitions.json")
            _write_gz(comp_path, payload)

        for season in catalogue_seasons():
            _fetch_statsbomb_file(
                client, "matches", f"{season['competition_id']}_{season['season_id']}"
            )

        matches = in_scope_matches()
        if sample is not None:
            barca = [
                m
                for m in matches
                if sources.BARCELONA
                in (m["home_team"]["home_team_name"], m["away_team"]["away_team_name"])
            ]
            matches = barca[-sample:]

        jobs: list[tuple[str, int]] = []
        for match in matches:
            jobs.append(("lineups", match["match_id"]))
            jobs.append(("events", match["match_id"]))
            if include_360 and match.get("match_status_360") == "available":
                jobs.append(("three-sixty", match["match_id"]))

        pending = [job for job in jobs if not statsbomb_path(*job).exists()]
        log.info("statsbomb: %d files required, %d to download", len(jobs), len(pending))
        _run_parallel(client, pending, workers)

    counts = {"matches_in_scope": len(matches)}
    for kind in ("lineups", "events", "three-sixty"):
        counts[kind] = len(list((config.RAW_STATSBOMB / kind).glob("*.json.gz")))
    return counts


def _run_parallel(client: httpx.Client, jobs: Iterable[tuple[str, int]], workers: int) -> None:
    jobs = list(jobs)
    if not jobs:
        return
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_fetch_statsbomb_file, client, kind, key): (kind, key) for kind, key in jobs
        }
        for future in as_completed(futures):
            future.result()
            done += 1
            if done % 100 == 0 or done == len(jobs):
                log.info("statsbomb: %d/%d files", done, len(jobs))


# football-data.co.uk ------------------------------------------------------------------


def football_data_path(season: sources.SeasonCode) -> Path:
    return (
        config.RAW_FOOTBALL_DATA
        / f"{sources.FOOTBALL_DATA_DIVISION}_{season.football_data_code}.csv"
    )


def fetch_football_data() -> int:
    config.ensure_dirs()
    fetched = 0
    with httpx.Client(timeout=_TIMEOUT) as client:
        for season in sources.football_data_seasons():
            target = football_data_path(season)
            if target.exists():
                continue
            url = (
                f"{sources.FOOTBALL_DATA_BASE_URL}/{season.football_data_code}/"
                f"{sources.FOOTBALL_DATA_DIVISION}.csv"
            )
            payload = _get(client, url)
            target.write_bytes(payload)
            fetched += 1
    return fetched


# Manifest ----------------------------------------------------------------------------


def write_manifest() -> Path:
    files = sorted(p for p in config.RAW.rglob("*") if p.is_file() and p.name != ".gitkeep")
    files = [p for p in files if p.name != "MANIFEST.json"]
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "statsbomb_commit": sources.STATSBOMB_COMMIT,
        "n_files": len(files),
        "files": {str(p.relative_to(config.RAW)): _sha256(p) for p in files},
    }
    target = config.RAW / "MANIFEST.json"
    target.write_text(json.dumps(manifest, indent=1))
    return target
