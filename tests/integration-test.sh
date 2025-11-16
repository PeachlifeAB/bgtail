#!/bin/bash
# Integration tests for bgtail

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR/.."
BGTAIL="bgtail"

# Disable Ghostty window for tests
export NO_WINDOW=1

# Enable logging
LOG_FILE="${TEST_LOG:-/tmp/bgtail-test-debug.log}"
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

log() {
    echo "[$(date -u +%H:%M:%S)] $*"
}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

TESTS_PASSED=0
TESTS_FAILED=0

pass() {
    local test_name="$1"
    echo -e "${GREEN}✓${NC} $test_name"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    log "PASS: $test_name"
}

fail() {
    local test_name="$1"
    local message="${2:-}"
    echo -e "${RED}✗${NC} $test_name"
    if [[ -n "$message" ]]; then
        echo "  $message"
    fi
    TESTS_FAILED=$((TESTS_FAILED + 1))
    log "FAIL: $test_name - $message"
}

require_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Missing required command: $cmd" >&2
        exit 1
    fi
}

# --- Test Sync Version (MUST RUN FIRST) ---
# Required by spec: install editable tool globally, then ensure bgtail --version matches
# bgtail <semver>.dev+d<YYYYMMDD> with YYYYMMDD derived from current git HEAD commit date.

testSyncVersion() {
    echo "=== TestSyncVersion: uv tool install -e . ==="
    log "TestSyncVersion: begin"

    require_cmd uv
    require_cmd git

    # Ensure we're in repo root for install.
    (cd "$REPO_ROOT" && uv tool install -e .)

    if ! command -v "$BGTAIL" >/dev/null 2>&1; then
        fail "test1AssureVersion" "bgtail not found on PATH after uv tool install -e ."
        return
    fi

    local expected_date
    expected_date=$(cd "$REPO_ROOT" && git log -1 --format=%cI | cut -c1-10 | tr -d '-')

    local version_out
    version_out=$($BGTAIL --version)

    local expected_prefix
    expected_prefix="bgtail "

    if [[ "$version_out" != ${expected_prefix}*".dev+d"${expected_date} ]]; then
        fail "test1AssureVersion" "Expected 'bgtail <semver>.dev+d${expected_date}', got: ${version_out}"
        return
    fi

    pass "test1AssureVersion"

    # Smoke test WITHOUT uv (must run globally installed from PATH)
    echo "=== Smoke (global bgtail, no uv) ==="
    $BGTAIL --version >/dev/null
    $BGTAIL python3 -c 'print("smoke")' >/dev/null
    pass "smokeGlobalInstall"

    log "TestSyncVersion: end"
    echo
}

log "=== Starting bgtail integration tests ==="
echo "Running bgtail integration tests..."
echo

testSyncVersion

testStartAndReconnect() {
    local test_name="testStartAndReconnect"
    log "$test_name: begin"

    # Run a trivial command in background (NO_WINDOW=1 already set)
    local out
    out=$($BGTAIL python3 -c 'print("hello")')

    local id
    id=$(printf "%s" "$out" | sed -n 's/^ID: //p' | head -n 1)
    local log_path
    log_path=$(printf "%s" "$out" | sed -n 's/^LOG: //p' | head -n 1)

    if [[ -z "$id" ]]; then
        fail "$test_name" "Could not extract ID from output: $out"
        return
    fi
    if [[ -z "$log_path" ]]; then
        fail "$test_name" "Could not extract LOG path from output: $out"
        return
    fi

    if [[ ! -f "$log_path" ]]; then
        fail "$test_name" "Expected log file to exist: $log_path"
        return
    fi

    # Bash command substitution strips trailing newlines, so compare file bytes via python.
    local log_repr
    log_repr=$(python3 -c 'import sys; from pathlib import Path; p=Path(sys.argv[1]); sys.stdout.write(repr(p.read_text()))' "$log_path")
    if [[ "$log_repr" != "'hello\\n'" ]]; then
        fail "$test_name" "Log file not pure output. Expected repr 'hello\\n', got: $log_repr"
        return
    fi

    # Reconnect should work without passing --project-log.
    local reconn
    reconn=$($BGTAIL --reconnect "$id")

    if ! printf "%s" "$reconn" | grep -q "^DONE$"; then
        fail "$test_name" "Reconnect output did not include DONE: $reconn"
        return
    fi

    pass "$test_name"
    log "$test_name: end"
    echo
}

testStartAndReconnect

# Summary
log "=== Test Summary ==="
echo "================================"
echo "Tests passed: $TESTS_PASSED"
echo "Tests failed: $TESTS_FAILED"
echo "================================"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    log "SUCCESS: All tests passed"
    exit 0
else
    echo -e "${RED}Some tests failed${NC}"
    log "FAILURE: $TESTS_FAILED tests failed"
    exit 1
fi
