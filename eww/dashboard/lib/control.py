#!/usr/bin/env python3
"""Command-line bridge for Bash, EWW and Orbit Studio."""
import argparse
import json
import sys

sys.dont_write_bytecode = True
from preferences import CONFIG, Invalid, defaults, migrate, read, save


def environment(p):
    pairs = {
        'DASHBOARD_NAME': p['profile']['name'], 'DASHBOARD_PROFILE_IMAGE': p['profile']['image'],
        'DASHBOARD_MONITOR': p['layout']['monitor'], 'DASHBOARD_WEATHER_LATITUDE': p['weather']['latitude'],
        'DASHBOARD_WEATHER_LONGITUDE': p['weather']['longitude'], 'DASHBOARD_WEATHER_UNIT': p['weather']['unit'],
        'DASHBOARD_WEATHER_REFRESH_SECONDS': p['weather']['refresh'], 'DASHBOARD_MUSIC_PLAYER': p['music']['player'],
        'DASHBOARD_MUSIC_DIRECTORY': p['music']['directory'], 'DASHBOARD_SEEK_SECONDS': p['music']['seek_seconds'],
        'DASHBOARD_CONFIRM_POWER_ACTIONS': int(p['behavior']['confirm_power']),
        'DASHBOARD_LOCK_BEFORE_SUSPEND': int(p['behavior']['lock_before_suspend']),
        'DASHBOARD_CLOSE_ON_LAUNCH': int(p['behavior']['close_on_launch']),
        'DASHBOARD_DISK_PATH': p['system']['disk'], 'DASHBOARD_CHECK_UPDATES': int(p['system']['updates']),
    }
    for key, field in [('DASHBOARD_BROWSER_COMMAND', 'browser'), ('DASHBOARD_FILE_MANAGER_COMMAND', 'file_manager'),
                       ('DASHBOARD_TERMINAL_COMMAND', 'terminal'), ('DASHBOARD_UPDATE_COMMAND', 'update_command')]:
        pairs[key] = p['advanced'][field] if p['advanced']['enabled'] else ''
    return pairs


def main():
    parser = argparse.ArgumentParser(description='Orbit settings and runtime bridge')
    parser.add_argument('action', choices=['json', 'env', 'init', 'validate', 'reset', 'render', 'clock', 'path'])
    args = parser.parse_args()
    try:
        if args.action == 'path':
            print(CONFIG)
            return
        if args.action == 'reset':
            save(defaults())
            return
        if args.action == 'env':
            try:
                p = read()
            except Invalid as exc:
                print(str(exc) + '\nUsing defaults; open Customize to repair settings.', file=sys.stderr)
                p = defaults()
            for key, value in environment(p).items():
                sys.stdout.write(key + '\0' + str(value) + '\0')
            return
        p = read()
        if args.action == 'json':
            print(json.dumps(p, ensure_ascii=False))
        elif args.action == 'init':
            if not CONFIG.exists():
                p, skipped = migrate()
                save(p)
                if skipped:
                    print('Legacy entries requiring manual review: ' + ', '.join(skipped), file=sys.stderr)
            print(CONFIG)
        elif args.action == 'validate':
            print('Configuration valid (schema 2)')
        elif args.action == 'render':
            from rendering import render
            print(render(p))
        elif args.action == 'clock':
            from datetime import datetime
            from zoneinfo import ZoneInfo
            now = datetime.now(ZoneInfo(p['clock']['timezone'])) if p['clock']['timezone'] else datetime.now().astimezone()
            print(json.dumps({'time': now.strftime('%H:%M' if p['clock']['format'] == '24h' else '%I:%M'),
                              'period': now.strftime('%p') if p['clock']['format'] == '12h' else '',
                              'date': now.strftime(p['clock']['date_format']).replace('\\', '\\\\')}))
    except (Invalid, OSError, ValueError) as exc:
        print(f'Orbit: {exc}', file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == '__main__':
    main()
