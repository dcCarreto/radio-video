# Development Guide

## Branches

| Branch | Purpose |
|---|---|
| `main` | Stable, released code. Updated only through pull requests from `dev`. |
| `dev` | Integration branch. Updated only through pull requests from working branches. |

Neither branch accepts direct pushes. All work happens on a working branch created from the
latest `dev`:

```
feature/<name>   new functionality
fix/<name>       bug fixes
refactor/<name>  internal restructuring without behavior changes
test/<name>      test additions or improvements
docs/<name>      documentation
chore/<name>     tooling, configuration, maintenance
perf/<name>      performance improvements
```

Names are lowercase English in kebab-case, for example `feature/conversion-queue`. CI rejects pull
requests whose branch name does not match this pattern, and pull requests into `main` that do not
come from `dev`.

## Workflow

1. `git switch dev && git pull`
2. `git switch -c feature/<name>`
3. Implement the change and its tests.
4. Run `pytest`, `ruff check .`, `ruff format --check .` and `mypy`.
5. Commit, push and open a pull request into `dev`.
6. Merge with **squash** once all checks pass and the change is approved.

Keep pull requests small and focused on one change.

## Commit Messages and Pull Request Titles

Use [Conventional Commits](https://www.conventionalcommits.org/). Pull requests into `dev` are
squash-merged, so the pull request title becomes the commit message on `dev` and drives the
release version.

```
feat: add conversion queue
fix(probe): handle files without a duration
docs: describe advanced mode settings
refactor!: replace settings storage format
```

| Type | Version bump |
|---|---|
| `feat` | minor |
| `fix`, `perf`, `refactor`, `docs`, `test`, `chore`, `ci`, `build` | patch |
| `!` after the type, or a `BREAKING CHANGE:` footer | major (minor while below 1.0.0) |

## Future Updates History

The `Future Updates` section of the README records every feature and fix pull request merged into
`dev`. After such a pull request is merged:

1. Create `docs/update-future-updates` from the latest `dev`.
2. Add an entry under the current date with the pull request number, title and a short
   description. Never remove or rewrite existing entries.
3. Open a pull request titled `docs: update future updates history` and merge it after checks
   pass. Delete the branch after merging.

Pull requests from `docs/update-future-updates` are never recorded in the history themselves, so
the process cannot recurse.

## Releases

1. Open a pull request from `dev` into `main` summarizing the changes since the last release.
2. Merge it with a **merge commit** (not squash) once all checks pass, so the individual commits
   remain visible to the release tooling.
3. The `Release` workflow then runs the full CI suite, computes the next version with
   [`scripts/next_version.py`](../scripts/next_version.py), creates the tag and the GitHub release
   with release notes and build artifacts.

The release is published by [`scripts/publish_release.py`](../scripts/publish_release.py), which
is idempotent and tolerates transient GitHub API failures:

- If a published release for the tag already exists, it does nothing.
- A leftover draft from an interrupted attempt is deleted and recreated.
- Failed attempts are retried. Because the API can report an error after the release was in fact
  published, the release state is checked after every failure.

Re-running the workflow is therefore always safe. Releases are never created manually.

After a release, open a pull request from a `chore/sync-main-into-dev` branch created from `main`
and merge it into `dev` with a merge commit, so the new tag is reachable from `dev`.

Release notes leave out repository bookkeeping: Future Updates history entries, `chore(release)`
commits and main-to-dev syncs.

## FFmpeg Location

`radio_video.ffmpeg.locate_tools()` looks for FFmpeg in this order:

1. The `RADIO_VIDEO_FFMPEG` and `RADIO_VIDEO_FFPROBE` environment variables. If set but invalid,
   lookup fails instead of silently falling back.
2. Directories passed explicitly by the caller (reserved for a bundled build).
3. The system `PATH`.

Tests that need FFmpeg use the `ffmpeg_tools`, `sample_video` and `sample_audio` fixtures from
`tests/conftest.py`. Sample media is generated at test time with FFmpeg's `lavfi` sources, so no
binary fixtures are stored in the repository. Locally these tests are skipped when FFmpeg is
missing; CI sets `RADIO_VIDEO_REQUIRE_FFMPEG=1` to make them fail instead.
