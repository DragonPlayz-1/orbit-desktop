#!/usr/bin/env bash
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
SOURCE_DIR="${REPO_ROOT}/eww/dashboard"
FONT_SOURCE="${REPO_ROOT}/fonts"
TARGET_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/eww/dashboard"
DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
FONT_TARGET="${DATA_HOME}/fonts/orbit-dashboard"
CHECK_ONLY=0 INSTALL_DEPS=0 SETUP=0
for option in "$@"; do
    case "${option}" in
        --check|--dry-run) CHECK_ONLY=1 ;; --install-deps) INSTALL_DEPS=1 ;; --setup) SETUP=1 ;;
        --help|-h) printf 'Usage: install.sh [--check|--dry-run] [--install-deps] [--setup]\nInstalls per-user with backups. EWW must already be installed.\n'; exit 0 ;;
        *) printf 'Unknown option: %s\n' "${option}" >&2; exit 64 ;;
    esac
done
if (( CHECK_ONLY && INSTALL_DEPS )); then printf '%s\n' '--check cannot be combined with --install-deps' >&2; exit 64; fi
if (( INSTALL_DEPS )); then
    if command -v apt-get >/dev/null; then sudo apt-get update && sudo apt-get install -y python3 jq curl util-linux xdg-utils zenity
    elif command -v pacman >/dev/null; then sudo pacman -S --needed python jq curl util-linux xdg-utils zenity
    elif command -v dnf >/dev/null; then sudo dnf install -y python3 jq curl util-linux xdg-utils zenity
    else printf 'Install Python 3.9+, jq, curl, util-linux and xdg-utils manually.\n' >&2; exit 1; fi
fi
for required in python3 jq curl flock timeout; do
    command -v "${required}" >/dev/null || { printf 'Required command missing: %s (use --install-deps)\n' "${required}" >&2; exit 1; }
done
python3 -c 'import sys; sys.exit(sys.version_info < (3,9))' || { printf 'Python 3.9+ is required.\n' >&2; exit 1; }
for required in eww.yuck eww.scss layout.yuck prefs.yuck lib/preferences.py lib/studio.py studio/index.html studio/app.js studio/style.css scripts/dashboard_doctor; do
    [[ -f "${SOURCE_DIR}/${required}" ]] || { printf 'Source file missing: %s\n' "${required}" >&2; exit 1; }
done
# shellcheck disable=SC1091
source "${SOURCE_DIR}/scripts/lib/common.sh"
binary="$(require_eww)" || exit 1
printf 'Using EWW %s at %s\n' "$(eww_version_label "$(eww_version "${binary}")")" "${binary}"
if (( CHECK_ONLY )); then
    config_control validate
    printf 'Source tree and EWW checks passed.\n'
    exit 0
fi
umask 077
mkdir -p -- "$(dirname -- "${TARGET_DIR}")" "${STATE_DIR}/backups"
exec 8>"${STATE_DIR}/install.lock"
flock -w 10 8 || { print_error 'An installation is already in progress.'; exit 1; }
stage="$(mktemp -d "$(dirname -- "${TARGET_DIR}")/.orbit-install.XXXXXX")"
backup='' installed=0 completed=0
rollback() {
    local status=$?
    if (( ! completed )); then
        (( ! installed )) || rm -rf -- "${TARGET_DIR}"
        [[ -z "${backup}" ]] || mv -- "${backup}" "${TARGET_DIR}"
        printf 'Installation failed; previous dashboard restored.\n' >&2
    fi
    rm -rf -- "${stage}"
    exit "${status}"
}
trap rollback EXIT
cp -a -- "${SOURCE_DIR}/." "${stage}/"
chmod 0755 "${stage}/launch_dashboard" "${stage}/scripts/"* 2>/dev/null || true
config_control init >/dev/null
# Validate everything before replacing an existing installation.
python3 "${stage}/lib/control.py" validate
# Stop our local settings companion before replacing its code on upgrade.
python3 "${stage}/lib/studio.py" --stop
if [[ -e "${TARGET_DIR}" || -L "${TARGET_DIR}" ]]; then
    previous="${STATE_DIR}/backups/dashboard-$(date +%Y%m%d-%H%M%S)-$$"
    mv -- "${TARGET_DIR}" "${previous}"
    backup=${previous}
fi
mv -- "${stage}" "${TARGET_DIR}"
installed=1
if [[ -d "${FONT_SOURCE}" ]]; then
    mkdir -p -- "${FONT_TARGET}"
    cp -a -- "${FONT_SOURCE}/." "${FONT_TARGET}/"
    if command -v fc-cache >/dev/null 2>&1; then
        fc-cache -f "${DATA_HOME}/fonts" >/dev/null 2>&1 || true
    fi
fi
"${TARGET_DIR}/scripts/dashboard_doctor"
# Desktop menu entries make subsequent launches independent of the terminal.
python3 - "${TARGET_DIR}" "${DATA_HOME}" <<'PY'
import pathlib, sys
target, data = map(pathlib.Path, sys.argv[1:])
apps = data / 'applications'
apps.mkdir(parents=True, exist_ok=True)
def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'
for filename, name, args in [('orbit-dashboard.desktop', 'Orbit Dashboard', ''), ('orbit-studio.desktop', 'Orbit Customize', ' --settings')]:
    (apps / filename).write_text('[Desktop Entry]\nType=Application\nName=' + name + '\nExec=' + quote(target / 'launch_dashboard') + args + '\nIcon=preferences-desktop\nTerminal=false\nCategories=Utility;Settings;\n', encoding='utf-8')
PY
completed=1
printf '\nInstalled. Open “Orbit Dashboard” or “Orbit Customize” from your application menu.\nSettings: %s\n' "${USER_CONFIG_FILE}"
[[ -z "${backup}" ]] || printf 'Previous installation: %s\n' "${backup}"
if (( SETUP )); then "${TARGET_DIR}/scripts/dashboard_settings"; fi
