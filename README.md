# bgtail

Run long-running commands in background with minimal CLI output (heartbeat dots) while streaming combined stdout/stderr to a log file.

## Install

### Dev (editable)

```bash
uv tool install -e .
```

### Release tag install

```bash
uv tool install git+https://github.com/PeachlifeAB/bgtail.git@0.1.0
```

## Usage

### Start a job

```bash
bgtail [--project-log|--global-log] [--stdin=inherit] <command> [args...]
```

- Default log dir: `./log/bgtail/`
- With `--project-log`: `./log/bgtail/` (explicit alias for the default)
- With `--global-log`: `/tmp/<CallerDirBasename>/`

bgtail prints an ID and log path, then prints a dot every 8 seconds until the job completes, then prints `DONE` and exits with the same exit code as the command.

### Reconnect

```bash
bgtail --reconnect <ID>
```

Reconnect resolves the log path for the given ID and prints dots (if still running) until completion.

### Options

- `--project-log` - Store logs under `./log/bgtail/` explicitly
- `--global-log` - Store logs under `/tmp/<CallerDirBasename>/`
- `--stdin=inherit` - Pass the caller's stdin through the detached runner to the target command. The caller owns the descriptor: closing it delivers EOF to the target, and bgtail does not retain it, synthesize input, or keep it open after caller or terminal disconnect. The default is closed stdin (`DEVNULL`).

## Help

```bash
bgtail --help
```
