# music-stuff

This project is a personal DJ toolchain that integrates Apple Music, beaTunes, djay, Spotify, and Essentia to analyse and manage music libraries.

## Getting started

You need [uv](https://docs.astral.sh/uv/) — it manages the Python version, virtualenv, and dependencies in one tool.

```bash
git clone <repo>
cd beatunes-dbviewer
uv sync
uv run pytest
```

That's it. If the tests pass you're ready.

## Formatting

```bash
uv run ruff format       # format code
uv run ruff check --fix  # fix lint issues
```

CI rejects unformatted code. Run these before pushing.

## Project layout

```
src/music_stuff/
  lib/              core libraries (one concern per file)
  *.py              CLI entry points
tests/              one test file per library module
data/               CSV exports and Essentia cache (not committed except cache)
scripts/            shell helpers for external tools
tmp/                contains clones of the beaTunes and djay databases
```

## Rules

**Use uv for everything.** Don't use `pip`, `poetry`, or `python` directly.

```bash
uv run pytest            # run tests
uv run djay-diff         # run a CLI tool
uv add <package>         # add a dependency
```

**Tests must pass before merging.** CI runs on both `macos-latest` and `ubuntu-latest`. Some tests require Music.app and are skipped automatically in CI — that's expected and fine. Don't break the ones that do run.

**Keep libraries single-concern.** Each file in `lib/` owns one integration or algorithm. Don't reach across them unless you're in a CLI script.

**Don't mock what you can test directly.** Prefer real in-process logic over mocked subprocess calls where possible. The existing Apple Music tests mock `subprocess.run` because osascript isn't available in CI — that's the right pattern for platform-specific calls.

**Secrets stay out of the repo.** Spotify credentials go in `secrets/` which is gitignored.

**Pin exact dependency versions.** Every entry in `pyproject.toml` uses `==`. When adding a package, pin the exact version that was installed (`uv pip show <package>` to find it). This avoids surprise breakage from transitive upgrades and keeps the environment reproducible across machines.

**Always work with the clones of the databases in ./tmp**

## Platform notes

Some code is macOS-only by design:

- `lib_apple_music.py` — requires osascript/JXA and Music.app
- `lib_clonefile.py` — uses `clonefile(2)` on macOS, falls back to `shutil.copy2` elsewhere
- `lib_beatunes.py` — reads from `~/Library/Application Support/beaTunes/`
- `lib_djay.py` — reads from `~/Music/djay/`

Tests for the macOS-only paths are marked `@needs_osascript` and skip gracefully when Music.app isn't running.

## Adding a new CLI tool

1. Create `src/music_stuff/your_tool.py` with a `main()` function.
2. Add an entry point in `pyproject.toml` under `[project.scripts]`.
3. Run `uv sync` to register it.
4. Add tests in `tests/test_your_tool.py` if the logic is non-trivial.

## Adding a new library module

1. Create `src/music_stuff/lib/lib_your_thing.py`.
2. Add `tests/test_lib_your_thing.py`.
3. Keep it focused — one external system or one algorithm per file.

**Document what you learn.** When you reverse-engineer a binary format, discover an API quirk, or figure out how an external tool works, add it to [NOTES.md](NOTES.md). Future-you will thank past-you.

See [NOTES.md](NOTES.md) for domain concepts, architecture decisions, and technical reference.
