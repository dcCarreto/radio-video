"""Create a GitHub release idempotently, tolerating transient API failures.

- Does nothing when a published release for the tag already exists.
- Deletes a leftover draft for the tag (from an interrupted earlier attempt) before creating.
- Retries failed attempts. The GitHub API can report an error after the release was actually
  published, so the state is checked after every failure before retrying.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from enum import Enum
from pathlib import Path

GhRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]

DEFAULT_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 15.0


class ReleaseState(Enum):
    MISSING = "missing"
    DRAFT = "draft"
    PUBLISHED = "published"


def run_gh(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=False)


def release_state(tag: str, gh: GhRunner) -> ReleaseState:
    result = gh(["release", "view", tag, "--json", "isDraft"])
    if result.returncode != 0:
        return ReleaseState.MISSING
    try:
        is_draft = json.loads(result.stdout)["isDraft"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return ReleaseState.MISSING
    return ReleaseState.DRAFT if is_draft else ReleaseState.PUBLISHED


def publish(
    tag: str,
    create_args: Sequence[str],
    gh: GhRunner = run_gh,
    attempts: int = DEFAULT_ATTEMPTS,
    delay: float = RETRY_DELAY_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> bool:
    """Publish the release. Returns True if it was created now, False if it already existed."""
    state = release_state(tag, gh)
    if state is ReleaseState.PUBLISHED:
        log(f"Release {tag} is already published; nothing to do.")
        return False

    for attempt in range(1, attempts + 1):
        if state is ReleaseState.DRAFT:
            log(f"Removing leftover draft release {tag}.")
            gh(["release", "delete", tag, "--yes"])

        result = gh(["release", "create", tag, *create_args])
        if result.returncode == 0:
            log(f"Published release {tag}.")
            return True

        log(f"Attempt {attempt} failed: {result.stderr.strip() or result.stdout.strip()}")
        state = release_state(tag, gh)
        if state is ReleaseState.PUBLISHED:
            log(f"Release {tag} was published despite the error.")
            return True
        if attempt < attempts:
            sleep(delay * attempt)

    raise RuntimeError(f"Could not publish release {tag} after {attempts} attempts")


def main(argv: Sequence[str] | None = None, gh: GhRunner = run_gh) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--notes-file", type=Path, required=True)
    parser.add_argument("--previous-tag", default="")
    parser.add_argument("assets", nargs="*", type=Path)
    args = parser.parse_args(argv)

    create_args = [
        "--target",
        args.target,
        "--title",
        args.title,
        "--notes-file",
        str(args.notes_file),
        "--generate-notes",
    ]
    if args.previous_tag:
        create_args += ["--notes-start-tag", args.previous_tag]
    create_args += [str(asset) for asset in args.assets]

    try:
        publish(args.tag, create_args, gh=gh)
    except RuntimeError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
