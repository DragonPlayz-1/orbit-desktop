"""Orbit preferences. Data only: never execute a configuration file."""
import contextlib
import copy
import fcntl
import json
import math
import os
from pathlib import Path
import re
import shlex
import tempfile
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
CONFIG_DIR = Path(os.environ.get('DASHBOARD_CONFIG_HOME', str(Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config')) / 'eww-dashboard')))
CONFIG = Path(os.environ.get('DASHBOARD_SETTINGS_FILE', str(CONFIG_DIR / 'settings.json')))
LEGACY = Path(os.environ.get('DASHBOARD_CONFIG_FILE', str(CONFIG_DIR / 'dashboard.conf')))
STATE = Path(os.environ.get('XDG_STATE_HOME', HOME / '.local/state')) / 'eww-dashboard'
CACHE = Path(os.environ.get('XDG_CACHE_HOME', HOME / '.cache')) / 'eww-dashboard'
RUNTIME = CACHE / 'runtime'
BACKUPS = STATE / 'config-backups'
CARDS = ['profile', 'clock', 'system', 'weather', 'music', 'apps', 'folders', 'links', 'uptime', 'power']
THEMES = {
    'aurora': ['#111827', '#1d293b', '#edf3ff', '#a8bad3', '#85dbcd'],
    'midnight': ['#0c1023', '#191e36', '#f2efff', '#b8b6d5', '#b5a2ff'],
    'graphite': ['#18191d', '#26282e', '#f3f4f6', '#b6b9c3', '#d6dbed'],
    'ember': ['#211716', '#352523', '#fff3eb', '#d9b9ac', '#ffb08c'],
    'ocean': ['#0a202b', '#15333f', '#edfaff', '#a0c6d3', '#7ed4f4'],
    'minimal': ['#edf0f5', '#ffffff', '#172033', '#536174', '#346759'],
}


def defaults():
    return {
        'version': 2, 'setup_complete': False,
        'profile': {'name': 'Your space', 'caption': 'Make room for what matters.', 'image': '', 'show_username': True},
        'appearance': {'preset': 'aurora', 'mode': 'dark', 'accent': '', 'background': '', 'font': 'Sans',
                       'font_size': 14, 'radius': 22, 'opacity': 96, 'shadow': True,
                       'reduced_motion': False, 'high_contrast': False},
        'layout': {'monitor': '0', 'columns': 3, 'density': 'balanced', 'width': 92, 'height': 88,
                   'cards': [{'id': name, 'label': name.title(), 'enabled': True} for name in CARDS]},
        'clock': {'format': '24h', 'date_format': '%A, %d %B', 'timezone': ''},
        'weather': {'place': '', 'latitude': '', 'longitude': '', 'unit': 'metric', 'refresh': 600},
        'music': {'player': '', 'directory': str(HOME / 'Music'), 'seek_seconds': 5, 'refresh': 3, 'artwork': True},
        'system': {'disk': '/', 'refresh': 3, 'updates': False},
        'behavior': {'close_on_launch': True, 'confirm_power': True, 'lock_before_suspend': True},
        'apps': [{'label': 'Browser', 'kind': 'default', 'target': 'browser', 'icon': 'WWW', 'enabled': True},
                 {'label': 'Files', 'kind': 'default', 'target': 'files', 'icon': 'DIR', 'enabled': True},
                 {'label': 'Terminal', 'kind': 'default', 'target': 'terminal', 'icon': '>_', 'enabled': True}],
        'links': [{'label': 'GitHub', 'url': 'https://github.com', 'icon': 'GH', 'enabled': True},
                  {'label': 'YouTube', 'url': 'https://www.youtube.com', 'icon': 'YT', 'enabled': True},
                  {'label': 'Mail', 'url': 'https://mail.google.com', 'icon': '@', 'enabled': True}],
        'folders': [{'label': n, 'path': str(p), 'icon': 'DIR', 'enabled': True}
                    for n, p in [('Home', HOME), ('Documents', HOME / 'Documents'), ('Downloads', HOME / 'Downloads')]],
        'advanced': {'enabled': False, 'browser': '', 'file_manager': '', 'terminal': '', 'update_command': ''},
    }


class Invalid(ValueError):
    pass


def validate(value):
    errors = []

    def check(ok, path, message):
        if not ok:
            errors.append(f'{path}: {message}')

    def shape(obj, template, path='settings'):
        if not isinstance(obj, dict):
            errors.append(f'{path}: expected an object')
            return
        for key in obj.keys() - template.keys():
            errors.append(f'{path}.{key}: unknown setting')
        for key, default in template.items():
            name = f'{path}.{key}'
            if key not in obj:
                errors.append(f'{name}: missing setting')
            elif isinstance(default, dict):
                shape(obj[key], default, name)
            elif type(obj[key]) is not type(default):
                errors.append(f'{name}: expected {type(default).__name__}')
            elif isinstance(default, str):
                check(len(obj[key]) <= 4096 and not any(ord(c) < 32 for c in obj[key]), name, 'use a single line of at most 4096 characters')

    shape(value, defaults())
    if errors:
        raise Invalid('\n'.join(errors))
    check(value['version'] == 2, 'version', 'this release supports settings version 2')
    check(not (value['weather']['latitude'] or value['weather']['longitude']) or bool(value['weather']['latitude'] and value['weather']['longitude']),
          'weather', 'enter both latitude and longitude, or clear both')

    def choice(section, key, values):
        check(value[section][key] in values, f'{section}.{key}', 'choose ' + ', '.join(map(str, values)))

    def number(section, key, lo, hi):
        check(lo <= value[section][key] <= hi, f'{section}.{key}', f'use a number between {lo} and {hi}')

    choice('appearance', 'preset', THEMES)
    choice('appearance', 'mode', ['dark', 'light'])
    choice('layout', 'density', ['compact', 'balanced', 'spacious'])
    choice('clock', 'format', ['12h', '24h'])
    choice('weather', 'unit', ['metric', 'imperial'])
    for section, key, lo, hi in [('appearance', 'font_size', 11, 24), ('appearance', 'radius', 0, 36),
                                 ('appearance', 'opacity', 70, 100), ('layout', 'columns', 1, 4),
                                 ('layout', 'width', 50, 100), ('layout', 'height', 50, 100),
                                 ('weather', 'refresh', 60, 86400), ('music', 'refresh', 2, 60),
                                 ('music', 'seek_seconds', 1, 60), ('system', 'refresh', 2, 60)]:
        number(section, key, lo, hi)
    a = value['appearance']
    check(not a['accent'] or re.fullmatch(r'#[0-9a-fA-F]{6}', a['accent']), 'appearance.accent', 'use #RRGGBB or leave blank')
    check(bool(re.fullmatch(r'[\w ,.-]{1,80}', a['font'])), 'appearance.font', 'use a font family name')
    check(bool(re.fullmatch(r'[\w .<>:-]{1,100}', value['layout']['monitor'])), 'layout.monitor', 'use an output name, index, or <primary>')
    if value['clock']['timezone']:
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(value['clock']['timezone'])
        except (ValueError, KeyError):
            errors.append('clock.timezone: use an IANA time zone such as Europe/London')
    coords = value['weather']
    if coords['latitude'] or coords['longitude']:
        for key, maximum in [('latitude', 90), ('longitude', 180)]:
            try:
                n = float(coords[key])
                check(math.isfinite(n) and -maximum <= n <= maximum, f'weather.{key}', f'use a number from -{maximum} to {maximum}')
            except ValueError:
                errors.append(f'weather.{key}: enter both coordinates or clear both')

    card_ids = []
    for i, card in enumerate(value['layout']['cards']):
        shape(card, {'id': '', 'label': '', 'enabled': True}, f'layout.cards[{i}]')
        if isinstance(card, dict):
            card_ids.append(card.get('id'))
            if isinstance(card.get('label'), str):
                check(0 < len(card['label']) <= 40, f'layout.cards[{i}].label', 'use 1–40 characters')
    check(len(card_ids) == len(CARDS) and set(x for x in card_ids if isinstance(x, str)) == set(CARDS), 'layout.cards', 'include each card exactly once')
    for collection, template in [('apps', {'label': '', 'kind': '', 'target': '', 'icon': '', 'enabled': True}),
                                 ('links', {'label': '', 'url': '', 'icon': '', 'enabled': True}),
                                 ('folders', {'label': '', 'path': '', 'icon': '', 'enabled': True})]:
        check(len(value[collection]) <= 24, collection, 'at most 24 shortcuts are supported')
        for i, row in enumerate(value[collection]):
            before = len(errors)
            shape(row, template, f'{collection}[{i}]')
            if before != len(errors):
                continue
            check(0 < len(row['label']) <= 60, collection, 'shortcut labels must contain 1–60 characters')
            check(len(row['icon']) <= 8, collection, 'use a short icon label (up to 8 characters)')
            if collection == 'links':
                try:
                    url = urlsplit(row['url'])
                    check(url.scheme in ('http', 'https') and bool(url.hostname) and not url.username, 'links.url', 'use an http:// or https:// address without credentials')
                except ValueError:
                    errors.append('links.url: invalid URL')
            elif collection == 'apps':
                check(row['kind'] in ('default', 'desktop', 'command'), 'apps.kind', 'choose default, desktop, or command')
                if row['kind'] == 'default':
                    check(row['target'] in ('browser', 'files', 'terminal'), 'apps.target', 'choose browser, files, or terminal')
                if row['kind'] == 'desktop':
                    check(bool(re.fullmatch(r'[\w. -]+\.desktop', row['target'])), 'apps.target', 'choose an installed application')
                if row['kind'] == 'command':
                    check(bool(row['target'].strip()), 'apps.target', 'enter a command')
    if errors:
        raise Invalid('\n'.join(errors))
    return copy.deepcopy(value)


def atomic(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        kwargs = {} if isinstance(text, bytes) else {'encoding': 'utf-8'}
        with os.fdopen(fd, 'wb' if isinstance(text, bytes) else 'w', **kwargs) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextlib.contextmanager
def locked():
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    with (CONFIG.parent / '.settings.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def read():
    if not CONFIG.exists():
        return migrate()[0]
    try:
        return validate(json.loads(CONFIG.read_text(encoding='utf-8')))
    except (ValueError, OSError) as exc:
        raise Invalid(f'{CONFIG}: {exc}') from exc


def backup():
    if CONFIG.exists():
        # Nanoseconds prevent two saves in the same second from losing history.
        atomic(BACKUPS / f'{time.time_ns()}.json', CONFIG.read_bytes())
        for old in sorted(BACKUPS.glob('*.json'))[:-20]:
            old.unlink()


def save(value):
    value = validate(value)
    with locked():
        backup()
        atomic(CONFIG, json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return value


def restore(name):
    if not re.fullmatch(r'\d+\.json', name):
        raise Invalid('Choose a saved backup')
    return save(json.loads((BACKUPS / name).read_text(encoding='utf-8')))


def migrate():
    result = defaults()
    skipped = []
    if not LEGACY.is_file():
        return result, skipped
    values = {}
    for line in LEGACY.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        m = re.fullmatch(r'\s*(DASHBOARD_[A-Z0-9_]+)=(.*)', line)
        if not m:
            skipped.append(line.split('=', 1)[0][:80])
            continue
        try:
            tokens = shlex.split(m[2], comments=True)
            if len(tokens) <= 1 and not any(c in m[2] for c in ('`', '$(', ';')):
                values[m[1]] = tokens[0] if tokens else ''
            else:
                skipped.append(m[1])
        except ValueError:
            skipped.append(m[1])
    mapping = {'NAME': ('profile', 'name'), 'PROFILE_IMAGE': ('profile', 'image'), 'MONITOR': ('layout', 'monitor'),
               'WEATHER_LATITUDE': ('weather', 'latitude'), 'WEATHER_LONGITUDE': ('weather', 'longitude'),
               'WEATHER_UNIT': ('weather', 'unit'), 'MUSIC_PLAYER': ('music', 'player'),
               'BROWSER_COMMAND': ('advanced', 'browser'), 'FILE_MANAGER_COMMAND': ('advanced', 'file_manager'),
               'TERMINAL_COMMAND': ('advanced', 'terminal'), 'UPDATE_COMMAND': ('advanced', 'update_command')}
    for old, (section, key) in mapping.items():
        if 'DASHBOARD_' + old in values:
            result[section][key] = values['DASHBOARD_' + old]
    if 'DASHBOARD_WEATHER_REFRESH_SECONDS' in values:
        try:
            result['weather']['refresh'] = int(values['DASHBOARD_WEATHER_REFRESH_SECONDS'])
        except ValueError:
            skipped.append('DASHBOARD_WEATHER_REFRESH_SECONDS')
    if values.get('DASHBOARD_CONFIRM_POWER_ACTIONS') in ('0', '1'):
        result['behavior']['confirm_power'] = values['DASHBOARD_CONFIRM_POWER_ACTIONS'] == '1'
    for key, val in values.items():
        if key.startswith('DASHBOARD_APP_') and key.endswith('_COMMAND') and val:
            result['apps'].append({'label': key[14:-8].replace('_', ' ').title(), 'kind': 'command', 'target': val, 'icon': '>_', 'enabled': False})
    # Imported shell commands remain visible for review but disabled by default.
    try:
        return validate(result), skipped
    except Invalid as exc:
        raise Invalid(f'Legacy settings need review in {LEGACY}: {exc}. Open Customize to reset or import corrected settings.') from exc


def palette(p):
    base, surface, text, muted, accent = THEMES[p['appearance']['preset']]
    if p['appearance']['mode'] == 'light':
        base, surface, text, muted = '#edf0f5', '#ffffff', '#172033', '#536174'
        accent = {'aurora': '#236653', 'midnight': '#6542b2', 'graphite': '#46536a', 'ember': '#994327', 'ocean': '#186981', 'minimal': '#346759'}[p['appearance']['preset']]
    elif p['appearance']['preset'] == 'minimal':
        base, surface, text, muted = THEMES['graphite'][:4]
    if p['appearance']['high_contrast']:
        base, surface, text, muted = ('#ffffff', '#ffffff', '#000000', '#252525') if p['appearance']['mode'] == 'light' else ('#000000', '#0b0b0b', '#ffffff', '#eeeeee')
    accent = p['appearance']['accent'] or accent
    if p['appearance']['high_contrast']:
        accent = '#174f3e' if p['appearance']['mode'] == 'light' else '#b4ffdd'
    channels = [int(accent[i:i+2], 16)/255 for i in (1, 3, 5)]
    linear = [c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in channels]
    luminance = sum(c*w for c, w in zip(linear, (.2126, .7152, .0722)))
    return dict(base=base, surface=surface, text=text, muted=muted, accent=accent, ink='#101820' if luminance > .179 else '#ffffff')
