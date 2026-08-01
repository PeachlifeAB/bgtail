from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _wait_for(path: Path, timeout: float = 3) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.01)
    pytest.fail(f"timed out waiting for {path}")


def _reader_script(tmp_path: Path) -> Path:
    script = tmp_path / "reader.py"
    script.write_text(
        """
from pathlib import Path
import sys

root = Path(sys.argv[1])
(root / "ready").write_text("", encoding="utf-8")
line = sys.stdin.readline()
if line:
    (root / "received").write_text(line, encoding="utf-8")
    sys.stdin.read()
(root / "eof").write_text("", encoding="utf-8")
""".lstrip(),
        encoding="utf-8",
    )
    return script


def _start_bgtail(tmp_path: Path, *args: str) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    return subprocess.Popen(
        [sys.executable, "-m", "bgtail.cli", "--no-log-popup", *args],
        cwd=tmp_path,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_for_exit(proc: subprocess.Popen[str]) -> tuple[str, str]:
    try:
        returncode = proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        pytest.fail("bgtail did not exit")
    assert returncode == 0
    assert proc.stdout is not None
    assert proc.stderr is not None
    return proc.stdout.read(), proc.stderr.read()


def test_default_detached_job_receives_eof(tmp_path: Path) -> None:
    script = _reader_script(tmp_path)
    proc = _start_bgtail(tmp_path, sys.executable, str(script), str(tmp_path))
    try:
        _wait_for(tmp_path / "ready")
        _wait_for(tmp_path / "eof")
        _wait_for_exit(proc)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_inherited_stdin_remains_open_until_caller_closes_it(tmp_path: Path) -> None:
    script = _reader_script(tmp_path)
    proc = _start_bgtail(
        tmp_path,
        "--stdin=inherit",
        sys.executable,
        str(script),
        str(tmp_path),
    )
    try:
        _wait_for(tmp_path / "ready")
        assert proc.stdin is not None
        proc.stdin.write("payload\n")
        proc.stdin.flush()
        _wait_for(tmp_path / "received")
        assert proc.poll() is None
        proc.stdin.close()
        _wait_for(tmp_path / "eof")
        _wait_for_exit(proc)
        assert (tmp_path / "received").read_text(encoding="utf-8") == "payload\n"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_help_documents_inherited_stdin_ownership() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "bgtail.cli", "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "--stdin=inherit" in proc.stdout
    assert "caller owns stdin" in proc.stdout
