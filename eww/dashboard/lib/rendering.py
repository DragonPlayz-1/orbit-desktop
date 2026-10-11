"""Compile validated preferences into EWW input, not shell fragments."""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
from preferences import ROOT, RUNTIME, atomic, locked, palette, validate
from displays import monitors, fitting_columns


def yuck(value):
    # Interpolation is evaluated even inside Yuck strings. Escape dollar signs.
    return json.dumps(str(value), ensure_ascii=False).replace('$', '\\$')


def command(*args):
    return yuck(shlex.join([str(a) for a in args]))


def label_text(value):
    # GTK label :text in EWW v0.6 performs a second unescape after evaluating
    # JSON/Yuck. Preserve literal backslashes without changing paths/commands.
    return str(value).replace('\\', '\\\\')


def render(p):
    p = validate(p)
    with locked():
        RUNTIME.mkdir(parents=True, exist_ok=True)
        for name in ('scripts', 'images'):
            path = RUNTIME / name
            source = ROOT / name
            if path.is_symlink() or path.exists():
                try:
                    current = path.resolve(strict=False)
                except OSError:
                    current = None
                if current == source.resolve():
                    continue
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink()
            path.symlink_to(source, target_is_directory=True)
        source = (ROOT / 'eww.yuck').read_text(encoding='utf-8')
        source = re.sub(r'(defpoll SYSTEM :interval )"[^"]+"', rf'\g<1>"{p["system"]["refresh"]}s"', source)
        source = re.sub(r'(defpoll MUSIC :interval )"[^"]+"', rf'\g<1>"{p["music"]["refresh"]}s"', source)
        source = source.replace(':width "92%" :height "88%"', f':width "{p["layout"]["width"]}%" :height "{p["layout"]["height"]}%"')
        # EWW v0.6 supports true/false here; the X11 backend ignores focusable.
        profile = p['profile']
        config = {
            'name': profile['name'], 'caption': profile['caption'], 'image': profile['image'] if Path(profile['image']).is_file() else str(ROOT / 'images/music.png'),
            'has_image': bool(profile['image']) and Path(profile['image']).is_file(), 'artwork': p['music']['artwork'],
            'username': os.environ.get('USER', '') if profile['show_username'] else '',
            'place': p['weather']['place'] or 'Your forecast',
            'settings': shlex.join([str(ROOT / 'scripts/dashboard_settings')]),
        }
        for key in ('name', 'caption', 'username', 'place'):
            config[key] = label_text(config[key])
        preferences_yuck = f'(defvar PREFS {yuck(json.dumps(config, ensure_ascii=False))})\n'
        cards = []
        for card in p['layout']['cards']:
            if not card['enabled']:
                continue
            name = card['id']
            content = f'({name})'
            if name in ('apps', 'folders', 'links'):
                rows = []
                for index, row in enumerate(p[name]):
                    if row['enabled']:
                        rows.append(f'(shortcut :label {yuck(label_text(row["label"]))} :icon {yuck(label_text(row["icon"]))} :action {command(ROOT / "scripts/dashboard_action", name, index)})')
                content = '(box :orientation "v" :spacing 6 ' + (' '.join(rows) if rows else '(label :class "muted" :text "Add shortcuts in Customize")') + ')'
            cards.append(f'(card :title {yuck(label_text(card["label"]))} {content})')
        # Row-major layout with equal-width columns. The body scrolls vertically
        # so large fonts and smaller displays never hide controls off screen.
        columns = fitting_columns(p, monitors())
        rows = []
        for start in range(0, len(cards), columns):
            row = cards[start:start + columns]
            row += ['(box)'] * (columns - len(row))
            rows.append('(box :orientation "h" :space-evenly true :spacing 14 ' + ' '.join(row) + ')')
        if not rows:
            rows = ['(label :class "empty-state" :text "A little room to breathe. Add cards in Customize." :wrap true :limit-width 40)']
        layout_yuck = '(defwidget dashboard_body [] (box :orientation "v" :space-evenly false :spacing 14 ' + ' '.join(rows) + '))\n'
        colors = palette(p)
        appearance = p['appearance']
        prefix = '\n'.join(f'${k}: {v};' for k, v in colors.items()) + '\n'
        # ASCII SCSS avoids Grass emitting @charset, which GTK3 rejects.
        font = ''.join(c if ord(c) < 128 else f'\\{ord(c):x} ' for c in appearance['font'])
        prefix += f'$font: "{font}";\n$font-size: {appearance["font_size"]}px;\n$radius: {appearance["radius"]}px;\n'
        prefix += f'$opacity: {appearance["opacity"] / 100};\n$pad: ' + {'compact': '12px', 'balanced': '20px', 'spacious': '28px'}[p['layout']['density']] + ';\n'
        prefix += '$motion: ' + ('0ms' if appearance['reduced_motion'] else '160ms') + ';\n'
        css = prefix + (ROOT / 'eww.scss').read_text(encoding='utf-8')
        if not appearance['shadow']:
            css += '\n.dashboard { box-shadow: none; }\n'
        background = Path(appearance['background']).expanduser()
        if appearance['background'] and background.is_file():
            # URI encoding prevents quotes, spaces and parentheses in file paths
            # from changing CSS syntax.
            css += f'\n.dashboard {{ background-image: url("{background.resolve().as_uri()}"); background-size: cover; }}\n'
        atomic(RUNTIME / 'eww.scss', css)
        # Publish a complete document in one rename. File-watch reloads cannot
        # observe mismatched preferences and layout while the user saves.
        source = source.replace('(include "prefs.yuck")', preferences_yuck).replace('(include "layout.yuck")', layout_yuck)
        atomic(RUNTIME / 'eww.yuck', source)
    return RUNTIME
