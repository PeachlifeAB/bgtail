from __future__ import annotations

from pathlib import Path

from bgtail.cli import _exit_path, _log_path, _runner


def test_runner_command_not_found_writes_exit_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    job_id = "test-not-found"
    exit_code = _runner(job_id, "project", ["does-not-exist-12345"])
    assert exit_code == 127
    exit_file = _exit_path(job_id, "project")
    assert exit_file.exists()
    assert exit_file.read_text(encoding="utf-8").strip() == "127"
    log_file = _log_path(job_id, "project")
    assert log_file.exists()
