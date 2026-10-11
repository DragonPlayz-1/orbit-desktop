#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
failures=0
warnings=0

pass() { printf '[PASS] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*"; warnings=$((warnings + 1)); }
fail() { printf '[FAIL] %s\n' "$*"; failures=$((failures + 1)); }

shopt -s nullglob
scripts=(
    "${ROOT_DIR}/tests/check.sh"
    "${ROOT_DIR}/install/"*.sh
    "${ROOT_DIR}/eww/dashboard/launch_dashboard"
    "${ROOT_DIR}/eww/dashboard/scripts/"*
    "${ROOT_DIR}/eww/dashboard/scripts/lib/"*
    "${ROOT_DIR}/tests/fixtures/eww"
)

for file in "${scripts[@]}"; do
    [[ -f "${file}" ]] || continue
    if bash -n "${file}"; then
        pass "bash syntax: ${file#"${ROOT_DIR}/"}"
    else
        fail "bash syntax: ${file#"${ROOT_DIR}/"}"
    fi
    [[ -x "${file}" ]] || warn "not executable: ${file#"${ROOT_DIR}/"}"
done

shell_scripts=()
for file in "${scripts[@]}"; do
    [[ -f "${file}" ]] && shell_scripts+=("${file}")
done

required_files=(
    "${ROOT_DIR}/eww/dashboard/eww.yuck"
    "${ROOT_DIR}/eww/dashboard/eww.scss"
    "${ROOT_DIR}/eww/dashboard/images/bg.jpg"
    "${ROOT_DIR}/eww/dashboard/images/music.png"
    "${ROOT_DIR}/config/dashboard.conf.example"
    "${ROOT_DIR}/install/install.sh"
    "${ROOT_DIR}/install/uninstall.sh"
)
for file in "${required_files[@]}"; do
    if [[ -f "${file}" ]]; then
        pass "required file: ${file#"${ROOT_DIR}/"}"
    else
        fail "missing file: ${file#"${ROOT_DIR}/"}"
    fi
done

if grep -R --line-number --fixed-strings 'github_pat_' \
    "${ROOT_DIR}/eww" "${ROOT_DIR}/install" "${ROOT_DIR}/config" "${ROOT_DIR}/.env.example" >/dev/null 2>&1; then
    fail 'credential-like GitHub token found in source files'
else
    pass 'no GitHub token pattern in source files'
fi

if grep -R --line-number --fixed-strings '/home/ishaan' \
    "${ROOT_DIR}/eww" "${ROOT_DIR}/install" >/dev/null 2>&1; then
    fail 'personal absolute path found in runtime files'
else
    pass 'no personal absolute path in runtime files'
fi

if grep -R --line-number --fixed-strings 'vw' "${ROOT_DIR}/eww/dashboard/eww.scss" >/dev/null 2>&1; then
    fail 'unsupported GTK viewport unit found in stylesheet'
else
    pass 'stylesheet uses GTK-compatible units'
fi

if grep -R --line-number --fixed-strings 'bg.png' \
    "${ROOT_DIR}/eww" "${ROOT_DIR}/install" >/dev/null 2>&1; then
    fail 'stale bg.png reference found'
else
    pass 'background asset reference is consistent'
fi

if grep -R --line-number --fixed-strings 'install/dashboard' \
    "${ROOT_DIR}/install" >/dev/null 2>&1; then
    fail 'installer still references the old source path'
else
    pass 'installer source path is repository-root aware'
fi

if grep -R --exclude-dir=__pycache__ --line-number --extended-regexp '/home/[A-Za-z0-9._-]+' \
    "${ROOT_DIR}/eww" "${ROOT_DIR}/install" >/dev/null 2>&1; then
    fail 'hardcoded home directory found in runtime files'
else
    pass 'runtime files have no hardcoded home directory'
fi

if python3 - "${ROOT_DIR}/eww/dashboard/eww.yuck" <<'PY'
import sys

path = sys.argv[1]
text = open(path, encoding="utf-8").read()
depth = 0
quoted = False
escaped = False
comment = False

for index, char in enumerate(text, 1):
    if comment:
        if char == "\n":
            comment = False
        continue
    if quoted:
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            quoted = False
        continue
    if char == ";" and index < len(text) and text[index] == ";":
        comment = True
        continue
    if char == '"':
        quoted = True
    elif char == "(":
        depth += 1
    elif char == ")":
        depth -= 1
        if depth < 0:
            raise SystemExit("closing parenthesis before opening parenthesis")

if quoted or depth != 0:
    raise SystemExit(f"unbalanced Yuck syntax: depth={depth}, quoted={quoted}")
PY
then
    pass 'Yuck parentheses are balanced'
else
    fail 'Yuck parentheses are not balanced'
fi

temporary_home="$(mktemp -d)"
trap 'rm -rf -- "${temporary_home}"' EXIT
runtime_env=(HOME="${temporary_home}/home" XDG_CONFIG_HOME="${temporary_home}/config" XDG_CACHE_HOME="${temporary_home}/cache" XDG_STATE_HOME="${temporary_home}/state")
mkdir -p "${temporary_home}/home"

if env "${runtime_env[@]}" "${ROOT_DIR}/eww/dashboard/scripts/dashboard_config" --root >/dev/null && \
   env "${runtime_env[@]}" "${ROOT_DIR}/eww/dashboard/scripts/sys_info" --cpu >/dev/null && \
   env "${runtime_env[@]}" "${ROOT_DIR}/eww/dashboard/scripts/weather_info" --stat >/dev/null && \
   env "${runtime_env[@]}" "${ROOT_DIR}/eww/dashboard/scripts/music_info" --backend >/dev/null; then
    pass 'runtime scripts execute with clean user paths'
else
    fail 'runtime scripts failed with clean user paths'
fi

check_eww_version() {
    local version=$1 expected_status=$2 expected_label=${3:-$1}
    local checker output status
    local -a check_command

    for checker in installer runtime; do
        if [[ "${checker}" == installer ]]; then
            check_command=("${ROOT_DIR}/install/install.sh" --check)
        else
            check_command=("${ROOT_DIR}/eww/dashboard/scripts/dashboard_doctor")
        fi

        if output="$(env "${runtime_env[@]}" \
            PATH="${ROOT_DIR}/tests/fixtures:${PATH}" \
            EWW_BIN="${ROOT_DIR}/tests/fixtures/eww" EWW_TEST_VERSION="${version}" \
            "${check_command[@]}" 2>&1)"; then
            status=0
        else
            status=$?
        fi

        if [[ "${status}" -ne "${expected_status}" ]]; then
            fail "${checker}: EWW '${version}' exited ${status}, expected ${expected_status}"
            printf '%s\n' "${output}"
        elif (( status == 0 )) && [[ "${output}" != *"EWW ${expected_label} at "* ]]; then
            fail "${checker}: EWW '${version}' diagnostic misreports the detected version"
            printf '%s\n' "${output}"
        else
            pass "${checker}: EWW version '${version}'"
        fi
    done
}

check_eww_version 0.4.0 1
check_eww_version 0.5.0 0 '0.5.0 (accepted for upstream v0.6.0 CLI compatibility)'
check_eww_version '0.5.0 abc1234' 0 '0.5.0 (accepted for upstream v0.6.0 CLI compatibility)'
check_eww_version 0.5.1 1
check_eww_version 0.6.0 0
check_eww_version 0.6.1 0
check_eww_version 1.0.0 0
check_eww_version unknown 1
check_eww_version '' 1

if command -v shellcheck >/dev/null 2>&1; then
    if shellcheck -x "${shell_scripts[@]}"; then
        pass 'ShellCheck'
    else
        fail 'ShellCheck'
    fi
else
    warn 'ShellCheck is not installed; CI installs it before running this check'
fi

if PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s "${ROOT_DIR}/tests" -p 'test_*.py'; then
    pass 'configuration, runtime, HTTP, and installation regression tests'
else
    fail 'behavioral regression tests'
fi
if command -v node >/dev/null 2>&1; then
    if node --check "${ROOT_DIR}/eww/dashboard/studio/app.js"; then pass 'Studio JavaScript syntax'; else fail 'Studio JavaScript syntax'; fi
fi

printf '\nResult: %s failure(s), %s warning(s)\n' "${failures}" "${warnings}"
(( failures == 0 ))
