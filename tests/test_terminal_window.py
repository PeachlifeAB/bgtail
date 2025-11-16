from __future__ import annotations

from pathlib import Path

from bgtail.cli import TerminalWindow, _close_window, _open_terminal_tail


class RunResult:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_open_terminal_tail_returns_window_and_tty(monkeypatch, tmp_path: Path) -> None:
    import bgtail.cli as cli

    monkeypatch.delenv("NO_WINDOW", raising=False)
    monkeypatch.delenv("SSH_CLIENT", raising=False)
    monkeypatch.delenv("SSH_TTY", raising=False)
    monkeypatch.delenv("SSH_CONNECTION", raising=False)

    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):  # noqa: ANN001
        calls.append(list(argv))
        return RunResult(stdout="0|17279|/dev/ttys007\n")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    window = _open_terminal_tail(tmp_path / "path with spaces.log")

    assert window == TerminalWindow(window_id="17279", tty="/dev/ttys007", quit_if_empty=True)
    assert calls
    assert calls[0][0] == "osascript"
    assert any('tell application "Terminal" to launch' == arg for arg in calls[0])
    assert any("exec /bin/zsh -lc" in arg for arg in calls[0])
    assert any("exec tail -f '" in arg and "path with spaces.log'" in arg for arg in calls[0])


def test_close_window_uses_terminal_ui_close(monkeypatch) -> None:
    import bgtail.cli as cli

    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):  # noqa: ANN001
        calls.append(list(argv))
        return RunResult()

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    _close_window(TerminalWindow(window_id="17279", tty="/dev/ttys007", quit_if_empty=True))

    assert calls[0][0] == "osascript"
    assert any('tell application "Terminal" to activate' == arg for arg in calls[0])
    assert any("frontmost of window id 17279" in arg for arg in calls[0])
    assert any("click button 1 of front window" in arg for arg in calls[0])
    assert any('click button "Terminate" of first sheet of front window' in arg for arg in calls[0])
    assert any("if true and (count of windows) is 0 then quit" in arg for arg in calls[0])
