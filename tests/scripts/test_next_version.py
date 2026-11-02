import pytest

from next_version import Bump, Commit, next_version, parse_version, release_notes


@pytest.mark.parametrize(
    ("message", "expected_type", "expected_breaking", "expected_bump"),
    [
        ("feat: add queue", "feat", False, Bump.MINOR),
        ("feat(ui): add queue", "feat", False, Bump.MINOR),
        ("fix: handle empty path", "fix", False, Bump.PATCH),
        ("refactor!: rename module", "refactor", True, Bump.MAJOR),
        ("feat: x\n\nBREAKING CHANGE: removed y", "feat", True, Bump.MAJOR),
        ("docs: update readme", "docs", False, Bump.PATCH),
        ("Update something", "other", False, Bump.PATCH),
    ],
)
def test_commit_parse(
    message: str, expected_type: str, expected_breaking: bool, expected_bump: Bump
) -> None:
    commit = Commit.parse(message)
    assert commit.type == expected_type
    assert commit.breaking is expected_breaking
    assert commit.bump is expected_bump


def test_initial_release() -> None:
    assert next_version(None, [Commit.parse("chore: init")]) == "0.1.0"


def test_no_commits_means_no_release() -> None:
    assert next_version(None, []) is None
    assert next_version("v1.2.3", []) is None


@pytest.mark.parametrize(
    ("previous", "messages", "expected"),
    [
        ("v1.2.3", ["fix: a"], "1.2.4"),
        ("v1.2.3", ["fix: a", "feat: b"], "1.3.0"),
        ("v1.2.3", ["feat!: b"], "2.0.0"),
        ("v0.4.1", ["feat!: b"], "0.5.0"),
        ("v0.4.1", ["docs: a"], "0.4.2"),
    ],
)
def test_next_version(previous: str, messages: list[str], expected: str) -> None:
    commits = [Commit.parse(message) for message in messages]
    assert next_version(previous, commits) == expected


def test_parse_version_rejects_invalid() -> None:
    with pytest.raises(ValueError, match="semantic version"):
        parse_version("v1.2")


def test_release_notes_groups_by_type() -> None:
    commits = [
        Commit.parse("feat: add queue (#4)"),
        Commit.parse("fix: progress parsing (#5)"),
        Commit.parse("feat!: new settings format (#6)"),
        Commit.parse("Merge pull request #7 from owner/dev"),
        Commit.parse("ci: cache pip"),
    ]
    notes = release_notes(commits)
    assert notes.index("### Breaking Changes") < notes.index("### Features")
    assert "- add queue (#4)" in notes
    assert "- progress parsing (#5)" in notes
    assert "- cache pip" in notes
    assert "Merge pull request" not in notes


def test_release_notes_skip_housekeeping() -> None:
    commits = [
        Commit.parse("feat: add queue (#21)"),
        Commit.parse("docs: update future updates history (#22)"),
        Commit.parse("chore(release): Radio/Video 0.2.0 (#23)"),
        Commit.parse("chore: sync main into dev after v0.1.0 (#20)"),
        Commit.parse("docs: describe advanced mode (#24)"),
    ]
    notes = release_notes(commits)
    assert "- add queue (#21)" in notes
    assert "- describe advanced mode (#24)" in notes
    assert "future updates" not in notes
    assert "Radio/Video 0.2.0" not in notes
    assert "sync main" not in notes


def test_housekeeping_still_counts_for_version_bump() -> None:
    commits = [Commit.parse("docs: update future updates history (#22)")]
    assert next_version("v0.1.0", commits) == "0.1.1"


def test_scope_is_parsed() -> None:
    assert Commit.parse("chore(release): Radio/Video 0.1.0").scope == "release"
    assert Commit.parse("feat: x").scope is None


def test_release_notes_empty() -> None:
    assert release_notes([]) == ""
