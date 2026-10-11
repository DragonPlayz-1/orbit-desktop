#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/eww/dashboard"
USER_CONFIG_DIR="${DASHBOARD_CONFIG_HOME:-${XDG_CONFIG_HOME:-${HOME}/.config}/eww-dashboard}"
CACHE_DIR="${XDG_CACHE_HOME:-${HOME}/.cache}/eww-dashboard"
STATE_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/eww-dashboard"
DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
FONT_TARGET="${DATA_HOME}/fonts/orbit-dashboard"
PURGE=0
YES=0

usage() {
    cat <<'EOF'
Usage: uninstall.sh [--purge] [--yes]

By default only the installed dashboard files are removed. User configuration,
cache, state, and backups are preserved.

  --purge  Also remove user configuration, cache, state, and bundled fonts.
  --yes    Required with --purge to confirm the destructive cleanup.
EOF
}

while (($#)); do
    case "$1" in
        --purge) PURGE=1 ;;
        --yes) YES=1 ;;
        --help|-h) usage; exit 0 ;;
        *) printf 'Unknown option: %s\n' "$1" >&2; exit 64 ;;
    esac
    shift
done

if (( PURGE && ! YES )); then
    printf 'Error: --purge requires --yes.\n' >&2
    exit 64
fi

if command -v "${EWW_BIN:-eww}" >/dev/null 2>&1; then
    timeout 5 "${EWW_BIN:-eww}" --config "${CACHE_DIR}/runtime" kill >/dev/null 2>&1 || true
fi
if [[ -f "${TARGET_DIR}/lib/studio.py" ]] && command -v python3 >/dev/null 2>&1; then
    python3 "${TARGET_DIR}/lib/studio.py" --stop
fi

rm -rf -- "${TARGET_DIR}"
rm -f -- "${DATA_HOME}/applications/orbit-dashboard.desktop" "${DATA_HOME}/applications/orbit-studio.desktop"

if (( PURGE )); then
    rm -rf -- "${USER_CONFIG_DIR}" "${CACHE_DIR}" "${STATE_DIR}" "${FONT_TARGET}"
    if command -v fc-cache >/dev/null 2>&1; then
        fc-cache -f "${HOME}/.local/share/fonts" >/dev/null 2>&1 || true
    fi
fi

printf 'Orbit Dashboard installation removed.\n'
if (( ! PURGE )); then
    printf 'User configuration, cache, state, backups, and fonts were preserved.\n'
fi
