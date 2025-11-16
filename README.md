# bgtail

Run long-running commands in background with minimal CLI output (heartbeat dots) while streaming combined stdout/stderr to a log file.

## Install

### Dev (editable)

```bash
uv tool install -e .
```

### Release tag install

```bash
uv tool install git+ssh://git@github.com/dabvid/bgtail.git@2.0.0
```

## Usage

### Start a job

```bash
bgtail [--project-log|--global-log] <command> [args...]
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

## Help

```bash
bgtail --help
```
