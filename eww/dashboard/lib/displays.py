"""Best-effort display discovery without adding Python GUI dependencies."""
import json
import os
import re
import subprocess


def monitors():
    def run(argv):
        return subprocess.check_output(argv, timeout=2, text=True, stderr=subprocess.DEVNULL)

    if os.environ.get('WAYLAND_DISPLAY'):
        for command in (['hyprctl', 'monitors', '-j'], ['swaymsg', '-t', 'get_outputs', '-r'], ['wlr-randr', '--json']):
            try:
                result = []
                for index, item in enumerate(json.loads(run(command))):
                    if item.get('disabled') or item.get('active') is False or item.get('enabled') is False:
                        continue
                    mode = item.get('rect') or item.get('current_mode') or next((m for m in item.get('modes', []) if m.get('current')), item)
                    scale = 1 if item.get('rect') else float(item.get('scale', 1))
                    width, height = int(mode['width'] / scale), int(mode['height'] / scale)
                    result.append({'name': item['name'], 'index': index, 'width': width, 'height': height})
                if result:
                    return result
            except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError, subprocess.SubprocessError):
                continue
    if os.environ.get('DISPLAY'):
        try:
            result = []
            for line in run(['xrandr', '--listmonitors']).splitlines():
                match = re.match(r'\s*(\d+):\s+\S+\s+(\d+)(?:/\d+)?x(\d+)(?:/\d+)?[+-]\d+[+-]\d+\s+(\S+)', line)
                if match:
                    index, width, height, name = match.groups()
                    scale = max(1, int(os.environ.get('GDK_SCALE', '1')))
                    result.append({'name': name, 'index': int(index), 'width': int(width) // scale, 'height': int(height) // scale})
            return result
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    return []


def fitting_columns(p, screens):
    selected = p['layout']['monitor']
    screen = next((s for s in screens if selected in (s['name'], str(s['index']))), None)
    if screen is None and selected == '<primary>' and screens:
        screen = screens[0]
    if not screen:
        return p['layout']['columns']
    # Keep enough logical pixels for readable cards at the chosen font size.
    available = screen['width'] * p['layout']['width'] / 100 - 64
    minimum = 300 * p['appearance']['font_size'] / 14
    return max(1, min(p['layout']['columns'], int(available / minimum)))
