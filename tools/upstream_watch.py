#!/usr/bin/env python3
"""Scan selected upstream repositories for character-rendering changes.

The scanner deliberately does not copy or merge upstream code. It compares a
reviewed baseline SHA with the current upstream branch and reports only files
matching the manifest's watch globs. This keeps upstream adoption explicit and
reviewable.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

DEFAULT_MANIFEST = Path("upstream/character-sources.json")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
GITHUB_API = "https://api.github.com"


class ManifestError(ValueError):
    """Raised when the upstream manifest is malformed."""


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read manifest {path}: {exc}") from exc

    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise ManifestError("manifest schemaVersion must be 1")

    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ManifestError("manifest sources must be a non-empty list")

    seen_ids: set[str] = set()
    for index, source in enumerate(sources):
        prefix = f"sources[{index}]"
        if not isinstance(source, dict):
            raise ManifestError(f"{prefix} must be an object")

        required_strings = (
            "id",
            "displayName",
            "repository",
            "branch",
            "baselineSha",
            "license",
            "licensePath",
            "integrationPolicy",
        )
        for key in required_strings:
            value = source.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ManifestError(f"{prefix}.{key} must be a non-empty string")

        source_id = source["id"]
        if source_id in seen_ids:
            raise ManifestError(f"duplicate source id: {source_id}")
        seen_ids.add(source_id)

        if source["repository"].count("/") != 1:
            raise ManifestError(f"{prefix}.repository must use owner/name form")
        if not SHA_RE.fullmatch(source["baselineSha"]):
            raise ManifestError(f"{prefix}.baselineSha must be a 40-character lowercase SHA")

        watch_paths = source.get("watchPaths")
        if not isinstance(watch_paths, list) or not watch_paths:
            raise ManifestError(f"{prefix}.watchPaths must be a non-empty list")
        if not all(isinstance(pattern, str) and pattern for pattern in watch_paths):
            raise ManifestError(f"{prefix}.watchPaths entries must be non-empty strings")

        focus = source.get("focus")
        if not isinstance(focus, list) or not focus or not all(
            isinstance(item, str) and item for item in focus
        ):
            raise ManifestError(f"{prefix}.focus must be a non-empty string list")

    return data


def matching_files(filenames: Iterable[str], patterns: Iterable[str]) -> list[str]:
    pattern_list = tuple(patterns)
    return sorted(
        {
            filename
            for filename in filenames
            if any(fnmatch.fnmatchcase(filename, pattern) for pattern in pattern_list)
        }
    )


def _request_json(url: str, token: str | None) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "hearthghost-upstream-watch",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API returned {exc.code} for {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub API request failed for {url}: {exc.reason}") from exc

    data = json.loads(payload)
    if not isinstance(data, dict):
        raise RuntimeError(f"unexpected GitHub API response for {url}")
    return data


def scan_source(source: dict[str, Any], token: str | None) -> dict[str, Any] | None:
    repository = source["repository"]
    branch = urllib.parse.quote(source["branch"], safe="")
    baseline = source["baselineSha"]

    head_data = _request_json(f"{GITHUB_API}/repos/{repository}/commits/{branch}", token)
    head = head_data.get("sha")
    if not isinstance(head, str) or not SHA_RE.fullmatch(head):
        raise RuntimeError(f"upstream {repository} returned an invalid head SHA")
    if head == baseline:
        return None

    compare_data = _request_json(
        f"{GITHUB_API}/repos/{repository}/compare/{baseline}...{head}", token
    )
    files = compare_data.get("files")
    if not isinstance(files, list):
        raise RuntimeError(f"upstream {repository} compare response has no file list")

    filenames = [
        item["filename"]
        for item in files
        if isinstance(item, dict) and isinstance(item.get("filename"), str)
    ]
    relevant = matching_files(filenames, source["watchPaths"])

    total_commits = compare_data.get("total_commits")
    compare_window_large = (
        isinstance(total_commits, int) and total_commits >= 250
    ) or len(files) >= 300

    if not relevant and not compare_window_large:
        return None

    return {
        "id": source["id"],
        "displayName": source["displayName"],
        "repository": repository,
        "branch": source["branch"],
        "baselineSha": baseline,
        "headSha": head,
        "license": source["license"],
        "integrationPolicy": source["integrationPolicy"],
        "focus": source["focus"],
        "watchPaths": source["watchPaths"],
        "changedFiles": relevant,
        "compareUrl": f"https://github.com/{repository}/compare/{baseline}...{head}",
        "compareWindowLarge": compare_window_large,
    }


def scan_manifest(manifest: dict[str, Any], token: str | None) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for source in manifest["sources"]:
        report = scan_source(source, token)
        if report is not None:
            reports.append(report)
    return reports


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="validate the manifest without network access")
    scan = subparsers.add_parser("scan", help="compare baselines with current upstream heads")
    scan.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    try:
        manifest = load_manifest(args.manifest)
        if args.command == "validate":
            print(f"validated {len(manifest['sources'])} upstream source(s)")
            return 0

        reports = scan_manifest(manifest, os.environ.get("GITHUB_TOKEN"))
        args.output.write_text(json.dumps(reports, indent=2) + "\n", encoding="utf-8")
        print(f"found {len(reports)} upstream source(s) needing review")
        return 0
    except (ManifestError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"upstream watch failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
