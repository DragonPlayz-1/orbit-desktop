"""Behavioral regression tests. All state and mocked integrations are isolated."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / 'eww/dashboard'
sys.path.insert(0, str(DASH / 'lib'))
import preferences as prefs
import rendering
import actions
import studio
import displays


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='orbit test ')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / 'config'),
                        XDG_CACHE_HOME=str(self.home / 'cache'), XDG_STATE_HOME=str(self.home / 'state'),
                        XDG_DATA_HOME=str(self.home / 'data'), DASHBOARD_SETTINGS_FILE=str(self.home / 'config/eww-dashboard/settings.json'),
                        DASHBOARD_CONFIG_FILE=str(self.home / 'config/eww-dashboard/dashboard.conf'),
                        EWW_BIN=str(ROOT / 'tests/fixtures/eww'), PATH=str(ROOT / 'tests/fixtures') + ':' + os.environ['PATH'])
        self.config = Path(self.env['DASHBOARD_SETTINGS_FILE'])
        values = {'HOME': self.home, 'CONFIG_DIR': self.config.parent, 'CONFIG': self.config,
                  'LEGACY': Path(self.env['DASHBOARD_CONFIG_FILE']), 'STATE': self.home / 'state/eww-dashboard',
                  'BACKUPS': self.home / 'state/eww-dashboard/config-backups', 'CACHE': self.home / 'cache/eww-dashboard',
                  'RUNTIME': self.home / 'cache/eww-dashboard/runtime'}
        for module in (prefs, rendering, studio, actions):
            for key, val in values.items():
                if hasattr(module, key):
                    patcher = patch.object(module, key, val)
                    patcher.start(); self.addCleanup(patcher.stop)
        self.p = prefs.defaults()

    def run_script(self, script, *args, ok=True, env=None):
        result = subprocess.run([str(ROOT / script), *args], env=env or self.env, text=True, capture_output=True, timeout=30)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def mock_command(self, name, text):
        directory = self.home / 'bin'
        directory.mkdir(exist_ok=True)
        path = directory / name
        path.write_text('#!/usr/bin/env bash\n' + text)
        path.chmod(0o755)
        self.env['PATH'] = str(directory) + ':' + self.env['PATH']
        return path


class PreferencesTests(Sandbox):
    def test_defaults_and_all_palettes(self):
        for name in prefs.THEMES:
            self.p['appearance']['preset'] = name
            self.assertEqual(prefs.validate(self.p), self.p)
            self.assertTrue(prefs.palette(self.p)['accent'].startswith('#'))

    def test_invalid_values_are_reported_before_normalization(self):
        for section, key, value in [('appearance', 'accent', 'red; x {}'), ('layout', 'columns', 9),
                                    ('weather', 'refresh', 0), ('clock', 'timezone', 'not/a/zone'),
                                    ('appearance', 'font_size', True), ('music', 'refresh', -1)]:
            candidate = copy.deepcopy(self.p); candidate[section][key] = value
            with self.subTest(key=key), self.assertRaises(prefs.Invalid): prefs.validate(candidate)

    def test_coordinate_validation(self):
        for latitude, longitude in [('91', '0'), ('0', '181'), ('nan', '0'), ('', '2'), ('north', 'east')]:
            self.p['weather'].update(latitude=latitude, longitude=longitude)
            with self.subTest(latitude=latitude), self.assertRaises(prefs.Invalid): prefs.validate(self.p)

    def test_bad_structure_and_unknown_fields(self):
        for candidate in [[], {'version': 90}, dict(self.p, extra=True), dict(self.p, profile=[]), dict(self.p, links=[{}])]:
            with self.subTest(candidate=type(candidate)), self.assertRaises(prefs.Invalid): prefs.validate(candidate)

    def test_duplicate_cards_rejected(self):
        self.p['layout']['cards'][0] = self.p['layout']['cards'][1]
        with self.assertRaises(prefs.Invalid): prefs.validate(self.p)

    def test_invalid_card_label_type_is_a_validation_error(self):
        self.p['layout']['cards'][0]['label'] = 12
        with self.assertRaises(prefs.Invalid): prefs.validate(self.p)

    def test_columns_fit_monitor_and_larger_fonts(self):
        self.p['layout']['columns'] = 4
        screens = [{'index': 0, 'name': 'DP-1', 'width': 1280, 'height': 720}]
        self.assertEqual(displays.fitting_columns(self.p, screens), 3)
        self.p['appearance']['font_size'] = 24
        self.assertEqual(displays.fitting_columns(self.p, screens), 2)
        self.p['layout']['monitor'] = 'DP-1'
        self.assertEqual(displays.fitting_columns(self.p, screens), 2)

    def test_render_refresh_and_unicode_font(self):
        self.p['music']['refresh'] = 9
        self.p['system']['refresh'] = 7
        self.p['appearance']['font'] = 'Noto 日本'
        path = rendering.render(self.p)
        self.assertIn('defpoll MUSIC :interval "9s"', (path / 'eww.yuck').read_text())
        self.assertIn('defpoll SYSTEM :interval "7s"', (path / 'eww.yuck').read_text())
        self.assertTrue((path / 'eww.scss').read_text().isascii())

    def test_urls_are_not_arbitrary_protocols(self):
        for url in ('javascript:alert(1)', 'file:///etc/passwd', 'https://user:pass@example.com', 'nope'):
            self.p['links'][0]['url'] = url
            with self.assertRaises(prefs.Invalid): prefs.validate(self.p)

    def test_save_backup_restore_and_permissions(self):
        prefs.save(self.p)
        self.p['profile']['name'] = 'Renée " $USER ${thing} \\ home'
        prefs.save(self.p)
        self.assertEqual(prefs.read()['profile']['name'], self.p['profile']['name'])
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        first = sorted(prefs.BACKUPS.glob('*.json'))[0].name
        prefs.restore(first)
        self.assertEqual(prefs.read()['profile']['name'], 'Your space')
        with self.assertRaises(prefs.Invalid): prefs.restore('../../elsewhere')

    def test_invalid_save_leaves_existing_intact(self):
        prefs.save(self.p); original = self.config.read_bytes()
        self.p['appearance']['radius'] = 100
        with self.assertRaises(prefs.Invalid): prefs.save(self.p)
        self.assertEqual(self.config.read_bytes(), original)

    def test_backup_retention(self):
        for i in range(24): self.p['profile']['name'] = str(i); prefs.save(self.p)
        self.assertEqual(len(list(prefs.BACKUPS.glob('*.json'))), 20)

    def test_legacy_is_never_executed_and_commands_are_disabled(self):
        prefs.LEGACY.parent.mkdir(parents=True)
        marker = self.home / 'executed'
        prefs.LEGACY.write_text(f'DASHBOARD_NAME="A Person"\nDASHBOARD_BROWSER_COMMAND="firefox"\ntouch "{marker}"\nDASHBOARD_MONITOR=$(touch "{marker}")\n')
        p, skipped = prefs.migrate()
        self.assertEqual(p['profile']['name'], 'A Person')
        self.assertEqual(p['advanced']['browser'], 'firefox')
        self.assertFalse(p['advanced']['enabled'])
        self.assertFalse(marker.exists()); self.assertEqual(len(skipped), 2)

    def test_broken_json_is_not_overwritten_by_read(self):
        self.config.parent.mkdir(parents=True); self.config.write_text('{broken')
        with self.assertRaises(prefs.Invalid): prefs.read()
        self.assertEqual(self.config.read_text(), '{broken')

    def test_render_escapes_untrusted_strings_and_applies_layout(self):
        self.p['profile']['name'] = '" ${oops} `touch /tmp/no`'
        self.p['layout']['cards'][0]['enabled'] = False
        self.p['layout']['columns'] = 1
        path = rendering.render(self.p)
        self.assertNotIn('(card :title "Profile" (profile))', (path / 'eww.yuck').read_text())
        self.assertNotIn('(include ', (path / 'eww.yuck').read_text())
        self.assertIn('\\${oops}', (path / 'eww.yuck').read_text())
        self.assertTrue((path / 'scripts').resolve() == DASH / 'scripts')
        self.assertIn('$radius: 22px;', (path / 'eww.scss').read_text())


class RuntimeTests(Sandbox):
    def test_failed_first_volume_backend_falls_through(self):
        self.mock_command('wpctl', 'exit 1\n')
        self.mock_command('pactl', 'if [[ "$1" == get-sink-mute ]]; then printf "Mute: no\\n"; else printf "Volume: 32768 / 50%%\\n"; fi\n')
        result = self.run_script('eww/dashboard/scripts/sys_info', '--volume')
        self.assertEqual(result.stdout.strip(), '50')

    def test_no_updates_does_not_crash(self):
        self.p['system']['updates'] = True; prefs.save(self.p)
        self.mock_command('checkupdates', 'exit 2\n'); self.mock_command('flatpak', 'exit 1\n')
        self.assertEqual(self.run_script('eww/dashboard/scripts/sys_info', '--updates').stdout.strip(), 'Up to date')

    def test_weather_stale_cache_and_location_isolation(self):
        self.p['weather'].update(latitude='1', longitude='2', refresh=60); prefs.save(self.p)
        curl = self.mock_command('curl', 'printf \'{"current":{"temperature_2m":21.5,"weather_code":0}}\'\n')
        first = json.loads(self.run_script('eww/dashboard/scripts/weather_info', '--json').stdout)
        self.assertEqual(first['temp'], '22°C')
        for path in prefs.CACHE.glob('weather/*.json'):
            data = json.loads(path.read_text()); data.update(timestamp=1, attempt=1); path.write_text(json.dumps(data))
        curl.write_text('#!/usr/bin/env bash\nexit 7\n')
        offline = json.loads(self.run_script('eww/dashboard/scripts/weather_info', '--json').stdout)
        self.assertEqual(offline['temp'], '22°C'); self.assertIn('Offline', offline['note'])
        self.p['weather']['latitude'] = '3'; prefs.save(self.p)
        other = json.loads(self.run_script('eww/dashboard/scripts/weather_info', '--json').stdout)
        self.assertEqual(other['temp'], '—'); self.assertEqual(other['status'], 'Forecast unavailable')

    def test_no_weather_does_not_request_network(self):
        marker = self.home / 'network'
        self.mock_command('curl', f'touch "{marker}"; exit 1\n')
        self.assertIn('Weather not configured', self.run_script('eww/dashboard/scripts/weather_info', '--json').stdout)
        self.assertFalse(marker.exists())

    def test_music_prefers_playing_and_uses_microseconds(self):
        self.mock_command('playerctl', '''if [[ "$1" == -l ]]; then printf 'paused\nplaying\n'; exit; fi
if [[ "$3" == status ]]; then [[ "$2" == playing ]] && printf 'Playing' || printf 'Paused';
elif [[ "$3" == position ]]; then printf '0.5';
elif [[ "$5" == '{{mpris:length}}' ]]; then printf '1000000';
elif [[ "$5" == '{{title}}' ]]; then printf '%s' "$2";
else printf 'Artist'; fi
''')
        data = json.loads(self.run_script('eww/dashboard/scripts/music_info', '--json').stdout)
        self.assertEqual(data['song'], 'playing'); self.assertEqual(data['progress'], 50); self.assertEqual(data['status'], 'Ⅱ')

    def test_scroll_seek_alias(self):
        marker = self.home / 'seek'
        self.mock_command('playerctl', f'if [[ "$1" == -l ]]; then printf "player"; elif [[ "$3" == status ]]; then printf "Playing"; elif [[ "$3" == position ]]; then printf "%s" "$4" > "{marker}"; fi\n')
        self.run_script('eww/dashboard/scripts/music_info', '--seek-up')
        self.assertEqual(marker.read_text(), '5+')

    def test_path_is_passed_as_argument_not_shell_source(self):
        folder = self.home / 'a " $(touch injected) folder'; folder.mkdir()
        self.p['folders'][0]['path'] = str(folder)
        with patch('actions.opener', return_value=['xdg-open']):
            argv = actions.resolve(self.p, 'folders', 0)
        self.assertEqual(argv, ['xdg-open', str(folder)])
        self.p['apps'][0].update(kind='command', target='touch injected')
        with self.assertRaises(prefs.Invalid): actions.resolve(self.p, 'apps', 0)

    def test_power_cancel_never_executes_systemctl(self):
        marker = self.home / 'power'
        self.mock_command('zenity', 'exit 1\n'); self.mock_command('systemctl', f'touch "{marker}"\n')
        self.run_script('eww/dashboard/scripts/power_action', '--poweroff')
        self.assertFalse(marker.exists())

    def test_suspend_aborts_when_lock_fails(self):
        marker = self.home / 'power'
        self.p['behavior']['confirm_power'] = False; prefs.save(self.p)
        self.mock_command('loginctl', 'exit 1\n')
        self.mock_command('systemctl', f'touch "{marker}"\n')
        self.env.pop('DISPLAY', None); self.env.pop('WAYLAND_DISPLAY', None)
        result = self.run_script('eww/dashboard/scripts/power_action', '--suspend', ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists())

    def test_confirmed_power_failure_is_reported(self):
        marker = self.home / 'power'
        self.mock_command('zenity', 'exit 0\n')
        self.mock_command('systemctl', f'printf "%s" "$1" > "{marker}"; exit 1\n')
        result = self.run_script('eww/dashboard/scripts/power_action', '--reboot', ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), 'reboot')
        self.assertIn('did not complete', result.stderr)

    def test_launcher_open_close_reload(self):
        self.run_script('eww/dashboard/launch_dashboard', '--open')
        state = prefs.RUNTIME / 'fixture-state.open'
        self.assertTrue(state.exists())
        self.run_script('eww/dashboard/launch_dashboard', '--reload'); self.assertTrue(state.exists())
        self.run_script('eww/dashboard/launch_dashboard'); self.assertFalse(state.exists())
        self.run_script('eww/dashboard/launch_dashboard', '--reload'); self.assertFalse(state.exists())

    def test_launcher_detects_false_success(self):
        self.env['EWW_TEST_FAIL_OPEN'] = '1'
        self.assertNotEqual(self.run_script('eww/dashboard/launch_dashboard', '--open', ok=False).returncode, 0)

    def test_install_upgrade_and_uninstall_preserve_settings(self):
        self.run_script('install/install.sh')
        self.p['profile']['name'] = 'Preserve me'; prefs.save(self.p)
        self.run_script('install/install.sh')
        self.assertEqual(prefs.read()['profile']['name'], 'Preserve me')
        self.assertTrue(list((prefs.STATE / 'backups').glob('dashboard-*')))
        self.assertTrue((self.home / 'data/applications/orbit-studio.desktop').exists())
        self.run_script('install/uninstall.sh')
        self.assertTrue(self.config.exists())
        self.assertFalse((self.home / 'config/eww/dashboard').exists())


class StudioTests(Sandbox):
    def setUp(self):
        super().setUp()
        prefs.save(self.p)
        from http.server import ThreadingHTTPServer
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), studio.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.server.server_close); self.addCleanup(self.server.shutdown)
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def request(self, route, data=None, token=True, origin=None):
        headers = {'X-Orbit-Token': studio.TOKEN} if token else {}
        if origin: headers['Origin'] = origin
        if data is not None: headers['Content-Type'] = 'application/json'
        request = Request(self.url + route, data=json.dumps(data).encode() if data is not None else None, headers=headers)
        return urlopen(request, timeout=5)

    def test_unauthenticated_and_cross_origin_requests_rejected(self):
        for token, origin in [(False, None), (True, 'https://unrelated.example')]:
            with self.assertRaises(HTTPError) as error: self.request('/api/state', token=token, origin=origin)
            self.assertEqual(error.exception.code, 403)

    def test_static_traversal_rejected(self):
        with self.assertRaises(HTTPError) as error: self.request('/../../etc/passwd')
        self.assertEqual(error.exception.code, 404)

    def test_import_is_validated_and_commands_start_disabled(self):
        self.p['advanced']['enabled'] = True
        imported = json.load(self.request('/api/import', {'settings': self.p}))
        self.assertFalse(imported['settings']['advanced']['enabled'])
        self.p['layout']['cards'][0]['label'] = None
        with self.assertRaises(HTTPError) as error:
            self.request('/api/import', {'settings': self.p})
        self.assertEqual(error.exception.code, 400)

    def test_non_image_upload_rejected(self):
        with self.assertRaises(HTTPError) as error:
            self.request('/api/upload', {'image': 'c2hlbGwgc2NyaXB0'})
        self.assertEqual(error.exception.code, 400)

    def test_state_save_conflict_and_invalid_save(self):
        state = json.load(self.request('/api/state'))
        self.p['profile']['name'] = 'Studio user'
        with patch('studio.apply', return_value='Applied'):
            saved = json.load(self.request('/api/save', {'revision': state['revision'], 'settings': self.p}))
        self.assertEqual(saved['settings']['profile']['name'], 'Studio user')
        with self.assertRaises(HTTPError) as error:
            self.request('/api/save', {'revision': state['revision'], 'settings': self.p})
        self.assertEqual(error.exception.code, 409)
        self.p['weather']['refresh'] = 1
        with self.assertRaises(HTTPError) as error:
            self.request('/api/save', {'revision': saved['revision'], 'settings': self.p})
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(prefs.read()['weather']['refresh'], 600)


if __name__ == '__main__':
    unittest.main()
