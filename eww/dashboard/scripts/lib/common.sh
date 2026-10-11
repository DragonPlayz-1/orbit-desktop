#!/usr/bin/env bash
# Shared Bash runtime. User preferences are parsed as data by the controller.
[[ -n "${ORBIT_COMMON_LOADED:-}" ]] && return 0
ORBIT_COMMON_LOADED=1
COMMON_DIR="$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_ROOT="$(cd -- "${COMMON_DIR}/../.." && pwd)"
CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"
CACHE_HOME="${XDG_CACHE_HOME:-${HOME}/.cache}"
STATE_HOME="${XDG_STATE_HOME:-${HOME}/.local/state}"
USER_CONFIG_DIR="${DASHBOARD_CONFIG_HOME:-${CONFIG_HOME}/eww-dashboard}"
# Used by diagnostic and installer scripts that source this library.
# shellcheck disable=SC2034
USER_CONFIG_FILE="${DASHBOARD_SETTINGS_FILE:-${USER_CONFIG_DIR}/settings.json}"
CACHE_DIR="${CACHE_HOME}/eww-dashboard"
STATE_DIR="${STATE_HOME}/eww-dashboard"
EWW_CONFIG="${CACHE_DIR}/runtime"
MIN_EWW_VERSION=0.6.0
umask 077
mkdir -p "${CACHE_DIR}" "${STATE_DIR}"

command_exists() { command -v "$1" >/dev/null 2>&1; }
print_error() { printf 'Orbit: %s\n' "$*" >&2; }
notify_user() {
    print_error "$1: ${2:-}"
    if command_exists notify-send; then
        notify-send --app-name='Orbit Dashboard' "$1" "${2:-}" >/dev/null 2>&1 || true
    fi
}
config_control() { PYTHONDONTWRITEBYTECODE=1 python3 "${DASHBOARD_ROOT}/lib/control.py" "$@"; }
load_user_config() {
    local key value
    while IFS= read -r -d '' key && IFS= read -r -d '' value; do
        [[ "${key}" == DASHBOARD_* ]] && printf -v "${key}" '%s' "${value}"
    done < <(config_control env)
}
eww_binary() { command -v "${EWW_BIN:-eww}" 2>/dev/null || true; }
eww_version() {
    local output
    output="$("${1:-eww}" --version 2>/dev/null)" || return 1
    if [[ "${output}" =~ ^eww[[:space:]]+v?([0-9]+\.[0-9]+\.[0-9]+)($|[[:space:]-]) ]]; then
        printf '%s\n' "${BASH_REMATCH[1]}"
    fi
}
eww_version_supported() {
    local major minor _patch
    [[ "$1" == 0.5.0 ]] && return 0
    IFS=. read -r major minor _patch <<< "$1"
    [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || return 1
    (( 10#${major} > 0 || 10#${minor} >= 6 ))
}
eww_version_label() {
    if [[ "$1" == 0.5.0 ]]; then
        printf '0.5.0 (accepted for upstream v0.6.0 CLI compatibility)\n'
    else
        printf '%s\n' "$1"
    fi
}
require_eww() {
    local binary version
    binary="$(eww_binary)"
    version="$(eww_version "${binary}")" || version=''
    if [[ -z "${binary}" || -z "${version}" ]] || ! eww_version_supported "${version}"; then
        print_error "EWW ${MIN_EWW_VERSION}+ is required; detected '${version:-unavailable}'. Install a supported EWW package."
        return 1
    fi
    printf '%s\n' "${binary}"
}
dashboard_eww() {
    local binary
    binary="$(require_eww)" || return 1
    timeout 15 "${binary}" --config "${EWW_CONFIG}" "$@"
}
active_dashboard_windows() { dashboard_eww active-windows 2>/dev/null; }
dashboard_is_open() {
    local windows
    windows="$(active_dashboard_windows)" || return 1
    [[ "${windows}" == *'dashboard: dashboard'* ]]
}
close_dashboard() { dashboard_eww close-all >/dev/null 2>&1 || true; }
close_after_launch() { [[ "${DASHBOARD_CLOSE_ON_LAUNCH}" == 1 ]] && close_dashboard; return 0; }
atomic_write() {
    local destination=$1 temporary
    mkdir -p -- "$(dirname -- "${destination}")"
    temporary="$(mktemp "${destination}.XXXXXX")" || return 1
    if cat > "${temporary}"; then
        mv -f -- "${temporary}" "${destination}"
    else
        rm -f -- "${temporary}"
        return 1
    fi
}
url_decode() { python3 -c 'import sys,urllib.parse; print(urllib.parse.unquote(sys.argv[1]))' "$1"; }
load_user_config
