# Architecture Decisions

## Runtime dependencies
Zero. Standard library only (`argparse`, `subprocess`, `signal`, `pathlib`, `dataclasses`).
The Homebrew formula installs with `uv pip install --no-deps`, which only works while this holds.
Principle: a background-process wrapper must not itself be a dependency-resolution problem. Adding a runtime dep breaks the packaging path, not just the import graph.

## Distribution
Homebrew formula in sibling repo `PeachlifeAB/homebrew-tap`, pinned to a GitHub **tag archive** with a recorded sha256. Not published to PyPI.
Tags are unprefixed (`0.1.0`); sibling target `sive` uses `v`-prefixed tags — do not copy its convention.
Principle: the formula pins an immutable artifact. Re-tagging changes the tarball hash and silently invalidates the pin, so tag once and treat a published tag as frozen.

## Release gating
`homebrew-tap/bin/preflight <formula>` is the single gate. It reads live git state for both repos, compares the formula's pinned sha256 against the live artifact, and runs `brew style` / `brew audit --strict`.
Run it immediately before every release; never release from remembered state.
Principle: release defects here come from stale assumptions, not bad code. Observed state beats recalled state, so the gate re-reads everything each run rather than trusting prior output.

## Version agreement
The version appears in four places that must agree: `pyproject.toml`, `bgtail/cli.py` `_BASE_VERSION`, `uv.lock`, and the git tag.
`tests/test_release_version.py` asserts CLI-vs-declared always, and tag-vs-declared on a tagged commit.
Principle: any value duplicated across files needs an executable check, or the copies drift. `uv.lock` was found holding `2.0.2` against `pyproject.toml`'s `0.1.0`.

## Process model
Caller spawns a detached runner that owns the child process; the caller prints heartbeat dots and exits with the child's exit code. Logs stream to a file, not the terminal.
Default stdin is `DEVNULL`; `--stdin=inherit` passes the caller's descriptor through without retaining or synthesizing input.
Principle: the caller must be disposable. Closing the terminal must not kill the job, and the runner must never own input it cannot honor after disconnect.

## Testing
Tests drive the real CLI through subprocess and observe files and exit codes — no mocking of internals.
Principle: the CLI *is* the public seam. Testing below it would couple tests to a module layout that is expected to change.

## Feature flags
None — direct deploy only. No provider, no flag config, no env-var gating.
Principle: a single-binary local CLI has no rollout surface; version pinning in the formula is the only rollback mechanism.
