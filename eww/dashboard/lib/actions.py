"""Launch desktop actions using argument arrays; shell commands are opt-in."""
import configparser
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys

sys.dont_write_bytecode = True
from preferences import STATE, Invalid, read


def applications():
    result = {}
    dirs = [Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))]
    dirs += [Path(p) for p in os.environ.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':') if p]
    for base in dirs:
        for path in sorted((base / 'applications').glob('**/*.desktop')):
            app_id = str(path.relative_to(base / 'applications')).replace('/', '-')
            if app_id in result:
                continue
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(path, encoding='utf-8')
                entry = parser['Desktop Entry']
                result[app_id] = None
                if entry.get('Type') != 'Application' or entry.get('Hidden') == 'true' or entry.get('NoDisplay') == 'true':
                    continue
                result[app_id] = {'id': app_id, 'name': entry.get('Name', app_id), 'path': str(path)}
            except (OSError, UnicodeError, configparser.Error, KeyError):
                continue
    return sorted((x for x in result.values() if x), key=lambda x: x['name'].lower())


def opener():
    if shutil.which('xdg-open'):
        return ['xdg-open']
    if shutil.which('gio'):
        return ['gio', 'open']
    raise Invalid('Install xdg-utils to open links and folders.')


def terminal():
    for name in ('x-terminal-emulator', 'kitty', 'alacritty', 'konsole', 'gnome-terminal', 'foot', 'xterm'):
        if shutil.which(name):
            return [name]
    raise Invalid('No terminal found. Choose a terminal in Advanced settings.')


def terminal_run(p, command):
    custom = p['advanced']['terminal'] if p['advanced']['enabled'] else ''
    argv = shlex.split(custom) if custom else terminal()
    if not argv:
        raise Invalid('No terminal found. Choose a terminal in Advanced settings.')
    name = Path(shutil.which(argv[0]) or argv[0]).resolve().name
    if name in ('gnome-terminal', 'gnome-terminal.wrapper'):
        return argv + ['--', 'bash', '-lc', command]
    if name == 'wezterm':
        return argv + ['start', '--', 'bash', '-lc', command]
    if name in ('kitty', 'foot'):
        return argv + ['bash', '-lc', command]
    if name in ('mate-terminal', 'xfce4-terminal'):
        return argv + ['--execute', 'bash', '-lc', command]
    return argv + ['-e', 'bash', '-lc', command]


def advanced_command(command, *args):
    # Positional arguments are not interpolated into shell source.
    return ['bash', '-c', command + ' "$@"', 'orbit', *args]


def resolve(p, collection, index):
    advanced = p['advanced']
    if collection == 'update':
        if not advanced['enabled'] or not advanced['update_command']:
            raise Invalid('Configure an update command in Customize → Advanced first.')
        return terminal_run(p, advanced['update_command'])
    if collection not in ('apps', 'links', 'folders') or not 0 <= index < len(p[collection]):
        raise Invalid('This shortcut no longer exists. Reopen the dashboard.')
    row = p[collection][index]
    if not row['enabled']:
        raise Invalid('This shortcut is disabled.')
    if collection == 'links':
        return advanced_command(advanced['browser'], row['url']) if advanced['enabled'] and advanced['browser'] else opener() + [row['url']]
    if collection == 'folders':
        path = Path(row['path']).expanduser().resolve()
        if not path.is_dir():
            raise Invalid(f'Folder not found: {path}. Choose another folder in Customize.')
        return advanced_command(advanced['file_manager'], str(path)) if advanced['enabled'] and advanced['file_manager'] else opener() + [str(path)]
    if row['kind'] == 'command':
        if not advanced['enabled']:
            raise Invalid('Enable Advanced commands in Customize to use this shortcut.')
        return ['bash', '-c', row['target']]
    if row['kind'] == 'desktop':
        for app in applications():
            if app['id'] == row['target']:
                if not shutil.which('gio'):
                    raise Invalid('Install GLib gio to launch desktop applications.')
                return ['gio', 'launch', app['path']]
        raise Invalid('Application is no longer installed. Choose a different application in Customize.')
    target = row['target']
    if target == 'terminal':
        return ['bash', '-c', advanced['terminal']] if advanced['enabled'] and advanced['terminal'] else terminal()
    if target == 'browser':
        return ['bash', '-c', advanced['browser']] if advanced['enabled'] and advanced['browser'] else opener() + ['https://www.startpage.com']
    return advanced_command(advanced['file_manager'], str(Path.home())) if advanced['enabled'] and advanced['file_manager'] else opener() + [str(Path.home())]


def launch(collection, index=0):
    argv = resolve(read(), collection, index)
    STATE.mkdir(parents=True, exist_ok=True)
    log = STATE / 'actions.log'
    if log.exists() and log.stat().st_size > 1024 * 1024:
        log.unlink()
    with log.open('ab') as out:
        proc = subprocess.Popen(argv, cwd=Path.home(), stdout=out, stderr=out, start_new_session=True)
    try:
        status = proc.wait(timeout=0.25)
        if status:
            raise Invalid(f'Application exited with status {status}. Details: {log}')
    except subprocess.TimeoutExpired:
        pass


if __name__ == '__main__':
    try:
        launch(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0)
    except (Invalid, OSError, ValueError, IndexError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
