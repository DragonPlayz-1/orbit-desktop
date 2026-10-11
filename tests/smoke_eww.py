#!/usr/bin/env python3
"""Real EWW smoke check; run under Xvfb or a headless Wayland compositor.

EWW_BIN=/path/to/eww xvfb-run -a -s '-screen 0 1366x768x24' \
    dbus-run-session -- python3 tests/smoke_eww.py
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / 'eww/dashboard'
EWW = shutil.which(os.environ.get('EWW_BIN', 'eww'))
if not EWW:
    raise SystemExit('Install a real supported EWW binary and set EWW_BIN.')


def assert_x11_window_fits(env):
    if env.get('WAYLAND_DISPLAY') or not shutil.which('xwininfo'):
        return
    root = run(['xwininfo', '-root'], env)
    tree = run(['xwininfo', '-root', '-tree'], env)
    width = int(re.search(r'Width:\s+(\d+)', root)[1])
    height = int(re.search(r'Height:\s+(\d+)', root)[1])
    match = re.search(r'"Eww - dashboard"[^\n]*?\s(\d+)x(\d+)[+-]', tree)
    assert match, tree
    assert int(match[1]) <= width and int(match[2]) <= height, f'Dashboard exceeds display: {match[0]}'


def run(argv, env, check=True):
    # A daemonized EWW fallback may inherit descriptors; file capture never
    # waits forever for a descendant to close the parent's stdout pipe.
    with tempfile.TemporaryFile(mode='w+') as out:
        result = subprocess.run(list(map(str, argv)), env=env, text=True, stdout=out, stderr=out, timeout=40)
        out.seek(0)
        text = out.read()
    if check and result.returncode:
        raise RuntimeError(text)
    return text


def retry(fn, predicate, description):
    for _ in range(60):
        value = fn()
        if predicate(value):
            return value
        time.sleep(.1)
    raise AssertionError(description)


with tempfile.TemporaryDirectory(prefix='orbit-eww-', dir=os.environ.get('ORBIT_TEST_TMP')) as temp:
    home = Path(temp)
    env = dict(os.environ, HOME=temp, XDG_CONFIG_HOME=str(home / 'config'), XDG_CACHE_HOME=str(home / 'cache'),
               XDG_STATE_HOME=str(home / 'state'), XDG_DATA_HOME=str(home / 'data'), EWW_BIN=EWW,
               PYTHONDONTWRITEBYTECODE='1', NO_AT_BRIDGE='1', PYTHONPATH=str(DASH / 'lib'))
    for key in ('DASHBOARD_CONFIG_HOME', 'DASHBOARD_CONFIG_FILE', 'DASHBOARD_SETTINGS_FILE'):
        env.pop(key, None)
    runtime = home / 'cache/eww-dashboard/runtime'
    config = home / 'config/eww-dashboard/settings.json'
    control = [sys.executable, DASH / 'lib/control.py']
    run([*control, 'init'], env)
    settings = json.loads(config.read_text())
    settings['layout']['monitor'] = os.environ.get('ORBIT_TEST_MONITOR', '0')
    run([*control, 'render'], env)
    log_path = home / 'daemon.log'
    with log_path.open('w') as log:
        daemon = subprocess.Popen([EWW, '--config', str(runtime), 'daemon', '--no-daemonize'], env=env, stdout=log, stderr=log)
    eww = [EWW, '--config', runtime]
    try:
        retry(lambda: run([*eww, 'ping'], env, False), lambda s: 'pong' in s, 'EWW did not become ready')
        for i, preset in enumerate(['aurora', 'midnight', 'graphite', 'ember', 'ocean', 'minimal']):
            print(f'Checking {preset}', flush=True)
            settings['appearance'].update(preset=preset, mode='light' if i % 2 else 'dark', font_size=24 if i == 5 else 14,
                                          reduced_motion=True, high_contrast=i == 4)
            settings['profile']['name'] = 'Renée " ${literal} \\ test'
            settings['layout']['cards'][0]['label'] = '${literal} profile'
            config.write_text(json.dumps(settings, ensure_ascii=False))
            run([DASH / 'launch_dashboard', '--open'], env)
            retry(lambda: run([*eww, 'active-windows'], env, False), lambda s: 'dashboard: dashboard' in s, 'Dashboard did not open')
            def live_state():
                try:
                    return json.loads(run([*eww, 'get', 'SYSTEM'], env, False))
                except ValueError:
                    return {}
            retry(live_state, lambda s: s.get('uptime', '--') != '--', 'System polling did not update')
            received = retry(lambda: run([*eww, 'get', 'PREFS'], env, False), bool, 'Preferences were not loaded')
            assert json.loads(received)['name'] == settings['profile']['name'].replace('\\', '\\\\'), 'User text changed during Yuck escaping'
            assert_x11_window_fits(env)
            if i == 0 and os.environ.get('ORBIT_DESKTOP_SCREENSHOT'):
                if env.get('WAYLAND_DISPLAY'):
                    run(['grim', os.environ['ORBIT_DESKTOP_SCREENSHOT']], env)
                else:
                    # Optional screenshot from an X11 test session (python3-gi).
                    import gi
                    gi.require_version('Gdk', '3.0')
                    from gi.repository import Gdk
                    display = Gdk.Display.get_default()
                    if display:
                        root = Gdk.get_default_root_window()
                        pixbuf = Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height())
                        pixbuf.savev(os.environ['ORBIT_DESKTOP_SCREENSHOT'], 'png', [], [])
            run([DASH / 'launch_dashboard', '--close'], env)
            retry(lambda: run([*eww, 'active-windows'], env, False), lambda s: not s.strip(), 'Dashboard did not close')
        # A fully hidden layout must still offer Customize and Close.
        for card in settings['layout']['cards']:
            card['enabled'] = False
        config.write_text(json.dumps(settings))
        run([DASH / 'launch_dashboard', '--open'], env)
        run([DASH / 'launch_dashboard', '--close'], env)
    except Exception:
        print(log_path.read_text(), file=sys.stderr)
        launcher_log = home / 'state/eww-dashboard/launcher.log'
        if launcher_log.exists():
            print(launcher_log.read_text(), file=sys.stderr)
        raise
    finally:
        run([*eww, 'kill'], env, False)
        try:
            daemon.wait(timeout=10)
        except subprocess.TimeoutExpired:
            daemon.terminate()
            daemon.wait(timeout=5)
    launcher_log = home / 'state/eww-dashboard/launcher.log'
    text = log_path.read_text() + (launcher_log.read_text() if launcher_log.exists() else '')
    log = re.sub(r'\x1b\[[0-9;]*m', '', text)
    # v0.6.0 has an upstream 100ms IPC response deadline, so slow GTK opens
    # can log 'channel closed' despite success. Actual windows and state are
    # verified above; every parse/style/widget/poll diagnostic still fails.
    problems = [line for line in log.splitlines() if re.search(r'(?i)(error:|warning:|unknown attribute|unknown variable|panic|Error while updating|Failed to run|failed to load)', line)]
    problems += [line for line in log.splitlines() if 'ERROR' in line and not any(known in line for known in ('sending response from main thread', 'Failed to send success response from application thread'))]
    if problems:
        print(log, file=sys.stderr)
        raise SystemExit('EWW configuration diagnostics found')
    print('PASS: real EWW, six themes, large text, literal user text, polling, empty layout, open and close')
