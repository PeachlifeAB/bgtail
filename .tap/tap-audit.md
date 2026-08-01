# TAP Audit
Last run: 2026-08-01
Codebase: bgtail

## Environments

bgtail is a locally-installed CLI, not a deployed service. The "environments"
that matter are install channels.

- Local (editable): `uv tool install -e .`
- Local (test):     `uv run pytest tests/`
- Release channel:  `brew install peachlifeab/tap/bgtail` → published via sibling repo `homebrew-tap`
- Preview:    not applicable
- Staging:    not applicable
- Production: not applicable (distribution is the Homebrew tap)

## Agent Harness Readiness

### Documentation
- CLAUDE.md: present, one line — `@AGENTS.md`. Delegation only.
- AGENTS.md: present via `.dog/AGENTS.md`. Strong on identity, principles, and
  binding rules. Covers harness, code principles (Hexagonal, CDD, DDAU, DI,
  DRY/SRP), and process. Does **not** document bgtail's own stack, run commands,
  or release process — those live in `.dog/` policy and `docs/RELEASING.md`.
- Architecture decisions: none discovered; `.tap/architecture.md` seeded by this audit.

### Strategic Context
- ✗ `.tap/product.md` exists
- ✗ ≤ 80 lines (n/a)
- ✗ `mtime` within 90 days (n/a)

Agents know *how* to work here (rules are unusually explicit) but nothing about
product direction: who uses bgtail, what is deliberately out of scope, or
whether the Homebrew tap is the only intended channel. Fix by running
`/tap-skills:curate-product-context`.

### MCP Servers (.mcp.json)
No `.mcp.json` in this repo. Servers are inherited from user-level config:
- ✓ codegraph → per-project symbol graph (no `.codegraph/` here, so inert)
- ✓ context-mode → sandboxed command execution and FTS5 indexing
- ✓ plane → issue tracking
- ✓ cloudflare → not relevant to this stack
- ✗ No repo-scoped MCP config, so server availability is machine-dependent
  rather than a property of the checkout.

### Skills
- ✓ Large user-level skill library (~50 skills) is visible.
- ✓ `homebrew-cask` / `homebrew-cask-authoring` — present but **not applicable**:
  bgtail ships as a *formula*, not a cask.
- ✗ `homebrew-formula` — present but **misleading for this repo**. It assumes a
  PyPI sdist workflow and references scripts (`homebrew-claude-mpm/scripts/…`,
  `mcp-vector-search/scripts/…`) that do not exist here. bgtail is **not on
  PyPI** (verified: 404); the tap pins GitHub tag archives. An agent following
  this skill verbatim would produce a wrong formula.
- ✗ No skill covers this repo's actual release path (tag → sha256 → tap formula
  → bottle). `docs/RELEASING.md` now fills that gap as documentation.

### CLI Tools
- ✓ uv, ruff, mypy, pytest, task, brew, gh, git — all present.
- ✗ `pytest-cov` — **absent**, which makes the declared coverage policy
  unenforceable (see Approach Gaps).

### Permissions (.claude/settings.json)
- Allowed: `mcp__plugin_context-mode_context-mode__ctx_execute` (in settings.local.json)
- Denied: nothing explicitly denied in settings; enforcement is via `.dog/hooks/policy.sh`
- Hooks: SessionStart, UserPromptSubmit, PreToolUse (Read|Edit|Write, Bash),
  PostToolUse (Edit|Write) — all routed through the Golden Dog harness.
- Missing: no `allow` entries for routine local commands (`uv run pytest`,
  `ruff`, `git status`), so ordinary verification prompts on each run.

Note: the hook layer is genuinely load-bearing here — during this audit it
blocked an `rm -rf` and flagged two real policy violations (a 268-line file, a
product doc referencing `.dog/`). This is a strength, not a gap.

### Test Infrastructure
- Unit/behavioral: 24 tests collected, all passing.
- Integration: `tests/integration-test.sh` present (shell-driven).
- Coverage: **not measurable** — `pytest --cov` fails, `pytest-cov` not installed.
- Browser/e2e: not applicable (CLI tool).
- Tests exercise real subprocess behavior through the CLI seam rather than
  internals, matching `.dog/rules/tests.md`.

### Design Complexity: Moderate to modify

Sampled the most-changed files (churn is low — 4 commits total in history).

- `bgtail/cli.py` — **582 lines, 14 imports.** Exceeds the repo's own
  `max_file_lines: 250` by 2.3×. Single module holding argument parsing,
  version formatting, log-path resolution, process spawning, terminal-window
  control, and reconnect logic.
- `bgtail/__init__.py` — 3 lines, entrypoint re-export only.
- `tests/*.py` — 17–119 lines each, one concern per file. Well factored.

The test suite is the healthy half of this codebase; the product code is a
single god module. `cli.py` is the one file an agent must touch for almost any
change, and it violates the policy the harness enforces on every write — an
agent editing it gets bitten by its own harness on unrelated work.

### Readiness Score: PARTIAL

An agent can implement, lint, typecheck, and run the full test suite
unsupervised, with an unusually strong hook layer catching policy violations in
real time. It **cannot** measure coverage (tooling absent), cannot rely on CI
(none exists), and cannot safely follow the available Homebrew skill (wrong
distribution model for this repo). Release work requires a sibling checkout
that nothing in this repo declares.

### Feedback Loops

#### 1. Release to Homebrew tap — Open (was: Manual)
- Generator: human edits version in 4 places (`pyproject.toml`, `cli.py`
  `_BASE_VERSION`, `uv.lock`, git tag), then hand-edits the sibling formula.
- Evaluator: `homebrew-tap/bin/preflight <formula>` — **added during this
  session**. Reads live git status/log/tags for both repos, compares the
  formula's pinned sha256 against the live artifact, runs `brew style` and
  `brew audit --strict`, and blocks on drift. Before this, the only evaluator
  was `brew test` running *after* publication.
- Handoff: `docs/RELEASING.md` — **added during this session**.
- Grading: exit code; 6 distinct blocking conditions.
- **Automate**: loop is now closed on *detection* but still open on *execution* —
  the version bump touches 4 files by hand. Next step: a `release:bump X.Y.Z`
  task that edits all four and runs `uv lock`, so the only manual act is
  choosing the number. Evidence this matters: `uv.lock` was found pinning
  `2.0.2` while `pyproject.toml` said `0.1.0`.

#### 2. Gate verification (fmt/lint/typecheck/tests) — Closed locally, No loop in CI
- Generator: agent edits code.
- Evaluator: `ruff format`, `ruff check`, `mypy bgtail`, `pytest tests/`, plus
  live hooks on every Edit/Write.
- Handoff: `.dog/sense.json` declares the gate list.
- Grading: exit codes — but `min_coverage_percent: 85` has **no evaluator**.
- **Automate**: add `pytest-cov` to dev dependencies and a `[tool.coverage]`
  section, then wire `--cov=bgtail --cov-fail-under=85`. Without it the policy
  is decorative. Second: no `.github/workflows/` means nothing runs on push —
  a single workflow calling the four gates would close this loop for
  contributors who don't run the harness.

#### 3. Formula correctness across 3 targets — Open
- Generator: human edits `Formula/*.rb` in the sibling tap.
- Evaluator: `brew style` / `brew audit --strict`, now invoked by preflight.
  Found **real pre-existing offenses in 2 of 3 formulas** (`bgtail.rb:13`,
  `lgtvctrl.rb:75` — both `Formula[...].opt_bin` instead of `formula_opt_bin`).
- Handoff: `homebrew-tap/docs/DEVELOPMENT.md`.
- Grading: exit code per formula.
- **Automate**: `brew audit --tap peachlifeab/tap` audits all three targets in
  one call — worth a `preflight --all` mode so a change to one formula does not
  leave the others unchecked.

## Approach Gaps

- **`cli.py` is 582 lines against a 250-line policy.** Every agent edit to the
  product code triggers a harness bite. Natural seams are visible: version
  formatting, log-path resolution, terminal-window control, and the runner each
  form a coherent module.
- **Coverage policy is unenforceable.** `min_coverage_percent: 85` is declared
  in `.dog/sense.json`, but `pytest-cov` is not installed and `--cov` errors
  out. Either install it or stop declaring the number.
- **No CI.** No `.github/workflows/`. Gates run only when someone runs them
  locally with the harness active.
- **`--version` always reports `.dev`.** `format_version()` unconditionally
  emits `bgtail X.Y.Z.dev+d<date>`; in a Homebrew build there is no `.git`, so
  the date silently falls back to *build time*. The formula's
  `assert_match "0.1.0"` passes anyway because it is a substring match, so no
  test catches it. Users of a tagged release see a `.dev` version.
- **No bottles for bgtail or sive.** `homebrew-tap/docs/DEVELOPMENT.md` states
  "Always build and upload a bottle for every formula release," but only
  `lgtvctrl` has a `bottle do` block. The documented rule and reality disagree;
  preflight now enforces the documented rule, which blocks both until bottles exist.
- **Sibling-repo dependency is undeclared.** Release work requires
  `homebrew-tap` checked out beside this repo. `.dog/sense.json` `paths[]` is
  specified as "every path/dependency, unconditionally, that can alter this
  project" and explicitly supports "sibling paths for multi-repo", but the tap
  is not listed.
- **The available `homebrew-formula` skill is wrong for this repo** (PyPI-based;
  bgtail is not on PyPI). An agent trusting it will produce an incorrect formula.

## Process

- Branching: single `main`. No feature branches in history (4 commits).
- CI: **none**. No `.github/workflows/`, no `gh run` history.
- Deploy: manual, multi-repo. Tag bgtail → publish → hand-copy sha256 into
  `homebrew-tap/Formula/bgtail.rb` → build/upload bottle → push tap.
  Now gated by `homebrew-tap/bin/preflight bgtail`.
- Release history quality: 4 of ~20 tap commits are corrections to a release
  just made (`56ed193`, `fef14f6`, `aa7a0bb`, `a8f85d1`) — a ~20% rework rate
  attributable to acting on remembered rather than observed state.

## Leverage Points

Goal: ship faster while maintaining quality bar.

### 1. Split `bgtail/cli.py` → unblocks every future edit
- Symptom: 582 lines vs. a 250-line policy; the harness bites on any write to it.
- Why it costs: it is the file every feature touches, so the friction is paid on
  every change, and the god-module shape makes agent edits riskier than they
  need to be.
- Fix: extract along existing seams — `version.py`, `logpath.py`, `window.py`,
  `runner.py`, leaving `cli.py` as argument parsing and orchestration. The test
  suite already covers behavior through the CLI seam, so the refactor is
  verifiable without writing new tests. ~2 hours.

### 2. Make the coverage gate real → stops a policy from being decorative
- Symptom: `min_coverage_percent: 85` declared; `pytest --cov` errors with
  "unrecognized arguments".
- Why it costs: a stated quality bar nobody can measure gives false confidence,
  and the 85% figure cannot inform whether the `cli.py` split is safe.
- Fix: add `pytest-cov` to dev dependencies, add `[tool.coverage.run]` with
  `source = ["bgtail"]`, run `pytest --cov=bgtail --cov-fail-under=85`. ~20 minutes.

### 3. Automate the version bump → removes the last hand-edited release step
- Symptom: version lives in 4 places; `uv.lock` was found stale at `2.0.2`
  against `pyproject.toml`'s `0.1.0`.
- Why it costs: preflight now *detects* this drift, but a human still has to fix
  it correctly under release pressure — the exact condition that produced the
  existing rework commits.
- Fix: a `release:bump X.Y.Z` task that rewrites `pyproject.toml` and
  `_BASE_VERSION`, runs `uv lock`, and leaves tagging to the human. ~45 minutes.

### 4. Add minimal CI → gates stop depending on who runs them
- Symptom: no `.github/workflows/`; the four gates run only locally.
- Why it costs: any contributor (or agent) without the Golden Dog harness active
  can push code that never saw `ruff`, `mypy`, or `pytest`.
- Fix: one workflow running `uv run ruff format --check .`, `ruff check .`,
  `mypy bgtail`, `pytest tests/` on push and PR. ~30 minutes.

### 5. Declare the tap in `.dog/sense.json` `paths[]` → makes the multi-repo dependency explicit
- Symptom: releasing requires a sibling `homebrew-tap` checkout that no config
  in this repo mentions.
- Why it costs: `task validate` cannot warn when the release path is broken, and
  a fresh agent has no way to discover the dependency short of reading git history.
- Fix: two `expected: "optional"` entries pointing at the tap's
  `Formula/bgtail.rb` and `docs/DEVELOPMENT.md`. ~5 minutes.
