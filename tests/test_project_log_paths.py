from __future__ import annotations

from pathlib import Path

from bgtail.cli import _log_dir, _log_path


def test_default_log_paths_use_project_log_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    assert _log_dir("default") == tmp_path / "log" / "bgtail"
    assert _log_path("job123", "default") == tmp_path / "log" / "bgtail" / "job123.log"


def test_project_log_paths_use_log_bgtail_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    assert _log_dir("project") == tmp_path / "log" / "bgtail"
    assert _log_path("job123", "project") == tmp_path / "log" / "bgtail" / "job123.log"
