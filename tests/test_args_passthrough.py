import pytest

from bgtail.cli import main


class PopenSpy:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):  # noqa: ANN001
        # Capture argv exactly as passed.
        self.calls.append(list(argv))

        class Proc:
            pid = 12345

            def wait(self) -> int:
                return 0

        return Proc()


def test_passthrough_preserves_argv_simple(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NO_WINDOW", "1")

    import bgtail.cli as cli

    spy = PopenSpy()
    monkeypatch.setattr(cli.subprocess, "Popen", spy)
    monkeypatch.setattr(cli, "_wait_for_exit_file", lambda job_id, use_project_log: 0)

    rc = main(["echo", "hello", "world"])
    assert rc == 0

    assert spy.calls
    # First Popen call is the detached runner process.
    runner_argv = spy.calls[0]
    import sys

    assert runner_argv[:3] == [sys.executable, "-m", "bgtail.cli"]
    assert "--_runner" in runner_argv
    assert "--" in runner_argv

    sep = runner_argv.index("--")
    forwarded = runner_argv[sep + 1 :]
    assert forwarded == ["echo", "hello", "world"]


@pytest.mark.parametrize(
    "argv",
    [
        ["python3", "-c", "print('a b')"],
        ["python3", "-c", "print(\"a b\")"],
        ["printf", "%s\\n", "a b"],
        ["echo", "x|y"],
        ["echo", "x&&y"],
        ["echo", "x;y"],
        ["echo", "$(whoami)"],
    ],
)
def test_passthrough_does_not_split_special_chars(monkeypatch, tmp_path, argv):
    """Shell metacharacters are just characters when passed as argv items."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NO_WINDOW", "1")

    import bgtail.cli as cli

    spy = PopenSpy()
    monkeypatch.setattr(cli.subprocess, "Popen", spy)
    monkeypatch.setattr(cli, "_wait_for_exit_file", lambda job_id, use_project_log: 0)

    rc = main(argv)
    assert rc == 0

    runner_argv = spy.calls[0]
    sep = runner_argv.index("--")
    forwarded = runner_argv[sep + 1 :]
    assert forwarded == argv


def test_passthrough_allows_leading_double_dash_sentinel(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NO_WINDOW", "1")

    import bgtail.cli as cli

    spy = PopenSpy()
    monkeypatch.setattr(cli.subprocess, "Popen", spy)
    monkeypatch.setattr(cli, "_wait_for_exit_file", lambda job_id, use_project_log: 0)

    rc = main(["--", "echo", "hello"])
    assert rc == 0

    runner_argv = spy.calls[0]
    sep = runner_argv.index("--")
    forwarded = runner_argv[sep + 1 :]
    assert forwarded == ["echo", "hello"]


def test_passthrough_runner_mode_forwards_exactly(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NO_WINDOW", "1")

    import bgtail.cli as cli

    spy = PopenSpy()
    monkeypatch.setattr(cli.subprocess, "Popen", spy)

    # Simulate runner invocation; it should call subprocess.Popen(cmd_argv, ...)
    rc = main(["--_runner", "job123", "--", "echo", "hello world"])
    assert rc == 0

    # First call should be the actual command argv.
    assert spy.calls == [["echo", "hello world"]]
