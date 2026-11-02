"""Determine the next release version from Conventional Commits since the last tag.

Writes ``version``, ``tag``, ``previous_tag`` and ``release`` to ``$GITHUB_OUTPUT``
when available and prints them otherwise. Release notes are written to the path
given with ``--notes``.

Bump rules:
- ``type!:`` or a ``BREAKING CHANGE:`` footer bumps MAJOR (MINOR while below 1.0.0).
- ``feat`` bumps MINOR.
- Anything else bumps PATCH.
- No commits since the last tag means no release.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

INITIAL_VERSION = "0.1.0"
TAG_PREFIX = "v"
COMMIT_SEPARATOR = "\x1e"

_HEADER = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?: (?P<subject>.+)$"
)
_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

SECTION_TITLES = {
    "breaking": "Breaking Changes",
    "feat": "Features",
    "fix": "Bug Fixes",
    "perf": "Performance",
    "refactor": "Refactoring",
    "docs": "Documentation",
}
OTHER_SECTION = "Other Changes"

# Repository bookkeeping that is not useful in release notes.
HOUSEKEEPING_SCOPES = {"release"}
HOUSEKEEPING_SUBJECTS = re.compile(r"^(Merge |update future updates history|sync main into dev)")


class Bump(IntEnum):
    NONE = 0
    PATCH = 1
    MINOR = 2
    MAJOR = 3


@dataclass(frozen=True)
class Commit:
    type: str
    subject: str
    breaking: bool
    scope: str | None = None

    @classmethod
    def parse(cls, message: str) -> Commit:
        lines = message.strip().splitlines()
        header = lines[0].strip() if lines else ""
        body = "\n".join(lines[1:])
        match = _HEADER.match(header)
        breaking = "BREAKING CHANGE:" in body or "BREAKING-CHANGE:" in body
        if match is None:
            return cls(type="other", subject=header, breaking=breaking)
        return cls(
            type=match["type"],
            subject=match["subject"],
            breaking=breaking or bool(match["breaking"]),
            scope=match["scope"],
        )

    @property
    def is_housekeeping(self) -> bool:
        return self.scope in HOUSEKEEPING_SCOPES or bool(HOUSEKEEPING_SUBJECTS.match(self.subject))

    @property
    def bump(self) -> Bump:
        if self.breaking:
            return Bump.MAJOR
        if self.type == "feat":
            return Bump.MINOR
        return Bump.PATCH


def parse_version(version: str) -> tuple[int, int, int]:
    match = _VERSION.match(version.removeprefix(TAG_PREFIX))
    if match is None:
        raise ValueError(f"Not a semantic version: {version!r}")
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def next_version(previous: str | None, commits: Sequence[Commit]) -> str | None:
    if previous is None:
        return INITIAL_VERSION if commits else None
    bump = max((commit.bump for commit in commits), default=Bump.NONE)
    if bump is Bump.NONE:
        return None
    major, minor, patch = parse_version(previous)
    if bump is Bump.MAJOR and major == 0:
        bump = Bump.MINOR
    if bump is Bump.MAJOR:
        return f"{major + 1}.0.0"
    if bump is Bump.MINOR:
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def release_notes(commits: Sequence[Commit]) -> str:
    sections: dict[str, list[str]] = {}
    for commit in commits:
        if commit.is_housekeeping and not commit.breaking:
            continue
        key = "breaking" if commit.breaking else commit.type
        title = SECTION_TITLES.get(key, OTHER_SECTION)
        sections.setdefault(title, []).append(commit.subject)
    order = [*SECTION_TITLES.values(), OTHER_SECTION]
    parts = []
    for title in order:
        if entries := sections.get(title):
            items = "\n".join(f"- {entry}" for entry in entries)
            parts.append(f"### {title}\n\n{items}")
    return "\n\n".join(parts) + "\n" if parts else ""


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def latest_tag() -> str | None:
    tags = _git("tag", "--merged", "HEAD", "--list", f"{TAG_PREFIX}*", "--sort=-v:refname")
    for tag in tags.split():
        if _VERSION.match(tag.removeprefix(TAG_PREFIX)):
            return tag
    return None


def commits_since(tag: str | None) -> list[Commit]:
    revision = f"{tag}..HEAD" if tag else "HEAD"
    output = _git("log", revision, f"--format=%B{COMMIT_SEPARATOR}")
    messages = [message for message in output.split(COMMIT_SEPARATOR) if message.strip()]
    return [Commit.parse(message) for message in messages]


def write_outputs(values: dict[str, str]) -> None:
    lines = "".join(f"{key}={value}\n" for key, value in values.items())
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as handle:
            handle.write(lines)
    sys.stdout.write(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--notes", type=Path, help="write release notes to this file")
    args = parser.parse_args(argv)

    previous = latest_tag()
    commits = commits_since(previous)
    version = next_version(previous, commits)
    if args.notes is not None:
        args.notes.write_text(release_notes(commits), encoding="utf-8")
    write_outputs(
        {
            "release": "true" if version else "false",
            "version": version or "",
            "tag": f"{TAG_PREFIX}{version}" if version else "",
            "previous_tag": previous or "",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
