"""Version agreement across the three places a release can drift.

The Homebrew formula's `test do` asserts that `bgtail --version` contains the
released tag. That assertion runs only after the release is public, so any
disagreement between pyproject.toml, the CLI, and the git tag is discovered too
late. These tests move that check before the release.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _declared_version() -> str:
    text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, re.MULTILINE)
    assert match, "pyproject.toml has no static version"
    return match.group(1)


def _cli_version_output() -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "bgtail.cli", "--version"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def test_cli_version_reports_declared_version() -> None:
    """`bgtail --version` must carry the version declared in pyproject.toml.

    This is the exact substring the Homebrew formula's `test do` asserts.
    """
    assert _declared_version() in _cli_version_output()


def test_exact_tag_checkout_matches_declared_version() -> None:
    """On a tagged commit, the tag must equal the declared version.

    Skipped off a tag: only a release build is required to agree. This is the
    check that would have caught the re-tag of 0.1.0 before the formula pinned
    a stale sha256.
    """
    try:
        tag = _git("describe", "--tags", "--exact-match")
    except subprocess.CalledProcessError:
        pytest.skip("HEAD is not a tagged commit; tag agreement not required")

    assert tag.lstrip("v") == _declared_version(), (
        f"git tag {tag} disagrees with pyproject version {_declared_version()}; "
        "the Homebrew formula test will fail after release"
    )
