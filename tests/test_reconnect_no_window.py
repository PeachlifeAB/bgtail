from __future__ import annotations

from pathlib import Path

from bgtail.cli import main


def test_reconnect_does_not_open_terminal_window(monkeypatch, tmp_path: Path) -> None:
    import bgtail.cli as cli

    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / "session.log"
    log_path.write_text("hello\n", encoding="utf-8")

    exit_dir = tmp_path / "log" / "bgtail" / ".bgtail"
    exit_dir.mkdir(parents=True)
    (exit_dir / "abc.exit").write_text("0\n", encoding="utf-8")

    opened = False

    def fake_open_terminal_tail(path: Path):  # noqa: ANN001
        nonlocal opened
        opened = True
        return None

    monkeypatch.setattr(cli, "_resolve_log_path", lambda job_id, log_mode: (log_path, "default"))
    monkeypatch.setattr(cli, "_open_terminal_tail", fake_open_terminal_tail)

    rc = main(["--reconnect", "abc"])

    assert rc == 0
    assert opened is False
