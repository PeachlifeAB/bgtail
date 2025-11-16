from __future__ import annotations

import argparse
import json
import os
import secrets
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal


_BASE_VERSION = "2.0.1"


LogMode = Literal["default", "project", "global"]


@dataclass(frozen=True)
class VersionInfo:
    base_version: str
    head_yyyymmdd: str


@dataclass(frozen=True)
class TerminalWindow:
    window_id: str
    tty: str
    quit_if_empty: bool


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _debug_log_path() -> Path:
    # Always-on debug logs for traceability.
    return Path.cwd() / "log" / "bgtail" / "debug.log"


def _debug(msg: str) -> None:
    ts = _utc_now().isoformat(timespec="milliseconds")
    path = _debug_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"{ts} {msg}\n")


def _git_head_yyyymmdd() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%cI"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:  # noqa: BLE001
        _debug(f"version: failed to read git head date: {exc}")
        return None

    iso = proc.stdout.strip()
    if not iso:
        return None

    try:
        dt = datetime.fromisoformat(iso)
    except ValueError as exc:
        _debug(f"version: invalid git iso date '{iso}': {exc}")
        return None

    return dt.astimezone(UTC).strftime("%Y%m%d")


def get_version_info() -> VersionInfo:
    yyyymmdd = _git_head_yyyymmdd()
    if yyyymmdd is None:
        yyyymmdd = _utc_now().strftime("%Y%m%d")
    return VersionInfo(base_version=_BASE_VERSION, head_yyyymmdd=yyyymmdd)


def format_version() -> str:
    vi = get_version_info()
    return f"bgtail {vi.base_version}.dev+d{vi.head_yyyymmdd}"


def _caller_dir_basename() -> str:
    return Path.cwd().name


def _make_id() -> str:
    now = _utc_now()
    return f"{now.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(4)}"


def _log_dir(log_mode: LogMode) -> Path:
    if log_mode == "global":
        return Path("/tmp") / _caller_dir_basename()
    return Path.cwd() / "log" / "bgtail"


def _log_path(job_id: str, log_mode: LogMode) -> Path:
    return _log_dir(log_mode) / f"{job_id}.log"


def _state_dir(log_mode: LogMode) -> Path:
    return _log_dir(log_mode) / ".bgtail"


def _pid_path(job_id: str, log_mode: LogMode) -> Path:
    return _state_dir(log_mode) / f"{job_id}.pid"


def _exit_path(job_id: str, log_mode: LogMode) -> Path:
    return _state_dir(log_mode) / f"{job_id}.exit"


def _resolve_log_path(job_id: str, log_mode: LogMode) -> tuple[Path, LogMode]:
    # requirements.md: reconnect resolves LOG path for <ID>.
    if log_mode != "default":
        return _log_path(job_id, log_mode), log_mode

    default_path = _log_path(job_id, "default")
    if default_path.exists():
        return default_path, "default"

    global_path = _log_path(job_id, "global")
    if global_path.exists():
        return global_path, "global"

    return default_path, "default"


def _should_open_window(no_window_flag: bool = False) -> bool:
    if no_window_flag:
        return False

    if os.environ.get("NO_WINDOW"):
        return False

    for key in ("SSH_CLIENT", "SSH_TTY", "SSH_CONNECTION"):
        if os.environ.get(key):
            return False

    return True


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _read_int(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:  # noqa: BLE001
        return None


def _terminal_zsh_command(command: str) -> str:
    return f"exec /bin/zsh -lc {shlex.quote(command)}"


def _open_terminal_tail(
    log_path: Path,
    exit_file: Path | None = None,
    *,
    no_window: bool = False,
) -> TerminalWindow | None:
    if not _should_open_window(no_window):
        return None

    if exit_file is not None:
        tail_cmd = (
            f"tail -f {shlex.quote(str(log_path))} & TAIL_PID=$!; "
            f"while [ ! -f {shlex.quote(str(exit_file))} ]; do sleep 1; done; "
            f"sleep 2; kill $TAIL_PID 2>/dev/null; exit"
        )
    else:
        tail_cmd = f"exec tail -f {shlex.quote(str(log_path))}"

    terminal_cmd = _terminal_zsh_command(tail_cmd)

    try:
        proc = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "Terminal" to launch',
                "-e",
                'tell application "Terminal" to set existingWindowCount to count of windows',
                "-e",
                'tell application "Terminal" to set createdTab to do script ""',
                "-e",
                "delay 1",
                "-e",
                f'tell application "Terminal" to do script {json.dumps(terminal_cmd)} in createdTab',
                "-e",
                'tell application "Terminal" to set createdWindowId to id of (first window whose tabs contains createdTab)',
                "-e",
                'tell application "Terminal" to set createdTTY to tty of createdTab',
                "-e",
                'tell application "Terminal" to activate',
                "-e",
                'return (existingWindowCount as text) & "|" & (createdWindowId as text) & "|" & createdTTY',
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        _debug("terminal: osascript not found; skipping window")
        return None

    if proc.returncode != 0:
        _debug(
            f"terminal: failed to open log window; stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
        return None

    output = proc.stdout.strip()
    if output.count("|") != 2:
        _debug(
            f"terminal: failed to parse window info; stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )
        return None

    existing_window_count_text, window_id, tty = output.split("|", 2)
    existing_window_count_text = existing_window_count_text.strip()
    window_id = window_id.strip()
    tty = tty.strip()
    if not existing_window_count_text or not window_id or not tty:
        _debug(f"terminal: incomplete window info; stdout={proc.stdout!r} stderr={proc.stderr!r}")
        return None

    try:
        existing_window_count = int(existing_window_count_text)
    except ValueError:
        _debug(f"terminal: invalid existing window count {existing_window_count_text!r}")
        return None

    return TerminalWindow(
        window_id=window_id,
        tty=tty,
        quit_if_empty=(existing_window_count == 0),
    )


def _close_window(window: TerminalWindow | None) -> None:
    if not window:
        return

    try:
        window_id = int(window.window_id)
    except ValueError:
        _debug(f"terminal: invalid window id {window.window_id!r}")
        return

    try:
        proc = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "Terminal" to activate',
                "-e",
                f'tell application "Terminal" to if (count of (every window whose id is {window_id})) > 0 then set frontmost of window id {window_id} to true',
                "-e",
                'tell application "System Events" to tell process "Terminal" to click button 1 of front window',
                "-e",
                "delay 0.5",
                "-e",
                'tell application "System Events" to tell process "Terminal" to if exists (first sheet of front window) then click button "Terminate" of first sheet of front window',
                "-e",
                "delay 0.5",
                "-e",
                f'tell application "Terminal" to if {str(window.quit_if_empty).lower()} and (count of windows) is 0 then quit',
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return

    if proc.returncode != 0:
        _debug(
            f"terminal: failed to close window {window_id}; stdout={proc.stdout!r} stderr={proc.stderr!r}"
        )


def _print_start_header(job_id: str, log_path: Path) -> None:
    print("bgtail will now run your command in background")
    print("and stream output to a log file.")
    print(f"ID: {job_id}")
    print(f"LOG: {log_path}")
    print("A dot will be added each 8 seconds as progress marker until completed.")
    print("To reconnect after timeout run:")
    print(f"bgtail --reconnect {job_id}")
    print("If anything hangs or for emergency cases use:")
    print(f"bgtail kill {job_id}")


def _print_reconnect_header(job_id: str, log_path: Path) -> None:
    print(f"Reconnecting to session {job_id}..")
    print()
    print(f"ID: {job_id}")
    print(f"LOG: {log_path}")
    print()
    print("To reconnect after timeout run:")
    print(f"bgtail --reconnect {job_id}")


def _print_footer(exit_code: int) -> None:
    print("IN PROGRESS: false")
    print(f"exit code {exit_code}")


def _wait_for_exit_file(job_id: str, log_mode: LogMode) -> int:
    exit_file = _exit_path(job_id, log_mode)

    while True:
        if exit_file.exists():
            code = _read_int(exit_file)
            if code is not None:
                return code
            return 1

        sys.stdout.write(".")
        sys.stdout.flush()
        time.sleep(8)


def _runner(job_id: str, log_mode: LogMode, cmd_argv: list[str]) -> int:
    log_path = _log_path(job_id, log_mode)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    exit_code = 1
    try:
        with open(log_path, "wb", buffering=0) as log_fh:
            try:
                proc = subprocess.Popen(
                    cmd_argv,
                    stdout=log_fh,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                    close_fds=True,
                )
            except FileNotFoundError as exc:
                _debug(f"runner: command not found {cmd_argv!r}: {exc}")
                exit_code = 127
            except PermissionError as exc:
                _debug(f"runner: permission denied starting {cmd_argv!r}: {exc}")
                exit_code = 126
            except OSError as exc:
                _debug(f"runner: failed to start {cmd_argv!r}: {exc}")
                exit_code = 1
            else:
                _write_text_atomic(_pid_path(job_id, log_mode), f"{proc.pid}\n")
                exit_code = proc.wait()
    except Exception as exc:  # noqa: BLE001
        _debug(f"runner: failed to run {cmd_argv!r}: {exc}")
        exit_code = 1

    try:
        _write_text_atomic(_exit_path(job_id, log_mode), f"{exit_code}\n")
    except Exception as exc:  # noqa: BLE001
        _debug(f"runner: failed to write exit file: {exc}")
    return exit_code


def _spawn_runner(job_id: str, log_mode: LogMode, cmd_argv: list[str]) -> None:
    runner_argv = [sys.executable, "-m", "bgtail.cli"]
    if log_mode == "project":
        runner_argv.append("--project-log")
    elif log_mode == "global":
        runner_argv.append("--global-log")

    runner_argv += ["--_runner", job_id, "--", *cmd_argv]

    subprocess.Popen(
        runner_argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


def _resolve_pid_path(job_id: str) -> Path | None:
    """Find PID file: check /tmp/*/.bgtail/<id>.pid then project-log."""
    # Check all /tmp subdirs (handles cross-project kills)
    tmp = Path("/tmp")
    if tmp.is_dir():
        try:
            subdirs = list(tmp.iterdir())
        except PermissionError:
            subdirs = []
        for subdir in subdirs:
            try:
                if subdir.is_dir():
                    pid_file = subdir / ".bgtail" / f"{job_id}.pid"
                    if pid_file.exists():
                        return pid_file
            except PermissionError:
                continue
    # Fallback: project-log path
    pid_file = _pid_path(job_id, "project")
    if pid_file.exists():
        return pid_file
    return None


def _kill_job(job_id: str) -> int:
    pid_file = _resolve_pid_path(job_id)
    if pid_file is None:
        print(f"Error: Unknown session id: {job_id}", file=sys.stderr)
        return 1
    pid = _read_int(pid_file)
    if pid is None:
        print(f"Error: corrupt pid file for {job_id}", file=sys.stderr)
        return 1
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        print(f"Process already dead (session {job_id})")
        return 0
    except PermissionError:
        print(f"Error: permission denied killing pid {pid}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    try:
        time.sleep(0.5)
        os.kill(pid, 0)
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except KeyboardInterrupt:
        return 130
    print(f"Killed session {job_id} (pid {pid})")
    return 0


def main(argv: list[str]) -> int:
    # Subcommand: kill
    if argv and argv[0] == "kill":
        if len(argv) < 2 or argv[1] in ("-h", "--help"):
            print("Usage: bgtail kill <ID>")
            return 0 if len(argv) > 1 else 1
        return _kill_job(argv[1])

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--help", "-h", action="store_true")
    parser.add_argument("--version", action="store_true")
    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument("--project-log", action="store_true")
    log_group.add_argument("--global-log", action="store_true")
    parser.add_argument("--reconnect")
    parser.add_argument("--no-log-popup", action="store_true")
    parser.add_argument("--_runner", action="store_true")
    parser.add_argument("rest", nargs=argparse.REMAINDER)

    ns = parser.parse_args(argv)

    if ns.version:
        print(format_version())
        return 0

    if ns.help:
        print("bgtail - Run commands detached with minimal heartbeat")
        print()
        print("USAGE:")
        print("    bgtail <command> [args...]")
        print("    bgtail --project-log <command> [args...]")
        print("    bgtail --global-log <command> [args...]")
        print("    bgtail --no-log-popup <command> [args...]")
        print("    bgtail --reconnect <ID>")
        print("    bgtail kill <ID>")
        print("    bgtail --version")
        print("    bgtail --help")
        return 0

    log_mode: LogMode = "default"
    if ns.project_log:
        log_mode = "project"
    elif ns.global_log:
        log_mode = "global"

    if ns._runner:
        if not ns.rest:
            return 1
        job_id = ns.rest[0]
        rest = ns.rest[1:]
        if rest[:1] == ["--"]:
            rest = rest[1:]
        if not rest:
            return 1
        return _runner(job_id, log_mode, rest)

    if ns.reconnect:
        job_id = ns.reconnect
        log_path, resolved_log_mode = _resolve_log_path(job_id, log_mode)
        if not log_path.exists():
            print(f"Error: Unknown session id: {job_id}", file=sys.stderr)
            return 1

        _print_reconnect_header(job_id, log_path)

        exit_file = _exit_path(job_id, resolved_log_mode)
        if exit_file.exists():
            code = _read_int(exit_file)
            print("DONE")
            _print_footer(code if code is not None else 1)
            return code if code is not None else 1

        code = _wait_for_exit_file(job_id, resolved_log_mode)
        sys.stdout.write("DONE\n")
        sys.stdout.flush()
        _print_footer(code)
        return code

    cmd_argv = ns.rest
    if cmd_argv[:1] == ["--"]:
        cmd_argv = cmd_argv[1:]

    if not cmd_argv:
        print("Error: No command provided", file=sys.stderr)
        print("Run 'bgtail --help' for usage", file=sys.stderr)
        return 1

    job_id = _make_id()
    log_path = _log_path(job_id, log_mode)

    _spawn_runner(job_id, log_mode, cmd_argv)

    window_id = _open_terminal_tail(
        log_path, exit_file=_exit_path(job_id, log_mode), no_window=ns.no_log_popup
    )
    _print_start_header(job_id, log_path)

    code = _wait_for_exit_file(job_id, log_mode)
    _close_window(window_id)

    sys.stdout.write("DONE\n")
    sys.stdout.flush()
    _print_footer(code)
    return code


def main_entry() -> None:
    raise SystemExit(main(sys.argv[1:]))


if __name__ == "__main__":
    main_entry()
