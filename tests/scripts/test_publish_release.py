from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

import publish_release
from publish_release import ReleaseState, publish, release_state

TAG = "v1.2.0"
CREATE_ARGS = ["--target", "abc123", "--title", "Radio/Video v1.2.0"]


class FakeGh:
    """Simulates the gh CLI with a scripted sequence of create outcomes."""

    def __init__(
        self,
        state: ReleaseState = ReleaseState.MISSING,
        create_results: Sequence[tuple[int, ReleaseState]] = ((0, ReleaseState.PUBLISHED),),
    ) -> None:
        self.state = state
        self.create_results = list(create_results)
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        command = args[1]
        if command == "view":
            if self.state is ReleaseState.MISSING:
                return subprocess.CompletedProcess(args, 1, "", "release not found")
            body = json.dumps({"isDraft": self.state is ReleaseState.DRAFT})
            return subprocess.CompletedProcess(args, 0, body, "")
        if command == "delete":
            self.state = ReleaseState.MISSING
            return subprocess.CompletedProcess(args, 0, "", "")
        if command == "create":
            code, self.state = self.create_results.pop(0)
            return subprocess.CompletedProcess(args, code, "", "HTTP 500" if code else "")
        raise AssertionError(f"unexpected gh call {args}")

    def commands(self) -> list[str]:
        return [call[1] for call in self.calls]


def _publish(gh: FakeGh, attempts: int = 3) -> bool:
    return publish(
        TAG, CREATE_ARGS, gh=gh, attempts=attempts, sleep=lambda _: None, log=lambda _: None
    )


def test_release_state() -> None:
    assert release_state(TAG, FakeGh(ReleaseState.MISSING)) is ReleaseState.MISSING
    assert release_state(TAG, FakeGh(ReleaseState.DRAFT)) is ReleaseState.DRAFT
    assert release_state(TAG, FakeGh(ReleaseState.PUBLISHED)) is ReleaseState.PUBLISHED


def test_creates_missing_release() -> None:
    gh = FakeGh()
    assert _publish(gh) is True
    assert gh.commands() == ["view", "create"]
    assert gh.calls[1] == ["release", "create", TAG, *CREATE_ARGS]


def test_existing_published_release_is_left_alone() -> None:
    gh = FakeGh(ReleaseState.PUBLISHED)
    assert _publish(gh) is False
    assert gh.commands() == ["view"]


def test_leftover_draft_is_replaced() -> None:
    gh = FakeGh(ReleaseState.DRAFT)
    assert _publish(gh) is True
    assert gh.commands() == ["view", "delete", "create"]


def test_error_after_successful_publish_is_accepted() -> None:
    gh = FakeGh(create_results=[(1, ReleaseState.PUBLISHED)])
    assert _publish(gh) is True
    assert gh.commands() == ["view", "create", "view"]


def test_retries_after_failure_that_left_a_draft() -> None:
    gh = FakeGh(create_results=[(1, ReleaseState.DRAFT), (0, ReleaseState.PUBLISHED)])
    assert _publish(gh) is True
    assert gh.commands() == ["view", "create", "view", "delete", "create"]


def test_command_line_builds_create_arguments() -> None:
    gh = FakeGh()
    exit_code = publish_release.main(
        [
            "--tag", "v0.2.0",
            "--title", "Radio/Video v0.2.0",
            "--target", "abc123",
            "--notes-file", "notes.md",
            "--previous-tag", "v0.1.0",
            "dist/a.whl", "dist/a.tar.gz",
        ],
        gh=gh,
    )  # fmt: skip
    assert exit_code == 0
    create = gh.calls[-1]
    assert create[:3] == ["release", "create", "v0.2.0"]
    assert create[create.index("--notes-start-tag") + 1] == "v0.1.0"
    assert "--generate-notes" in create
    assert create[-2:] == [str(Path("dist/a.whl")), str(Path("dist/a.tar.gz"))]


def test_command_line_without_previous_tag() -> None:
    gh = FakeGh()
    args = ["--tag", "v0.1.0", "--title", "t", "--target", "abc", "--notes-file", "n.md"]
    assert publish_release.main([*args, "--previous-tag", ""], gh=gh) == 0
    assert "--notes-start-tag" not in gh.calls[-1]


def test_gives_up_after_all_attempts() -> None:
    gh = FakeGh(create_results=[(1, ReleaseState.MISSING)] * 3)
    with pytest.raises(RuntimeError, match="after 3 attempts"):
        _publish(gh)
    assert gh.commands().count("create") == 3
