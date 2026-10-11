#!/usr/bin/env python3
"""Local Orbit Studio. Standard library only; binds exclusively to loopback."""
import argparse
import base64
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
import secrets
import shutil
import subprocess
import sys
import threading
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen

sys.dont_write_bytecode = True
from actions import applications, launch
from displays import monitors
from preferences import BACKUPS, CONFIG, CONFIG_DIR, ROOT, STATE, THEMES, Invalid, atomic, defaults, migrate, read, restore, save, validate
from rendering import render

STATIC = ROOT / 'studio'
TOKEN = secrets.token_urlsafe(32)
WRITE_LOCK = threading.Lock()


def revision():
    return hashlib.sha256(CONFIG.read_bytes() if CONFIG.exists() else b'').hexdigest()


def apply(p):
    try:
        render(p)
    except (OSError, ValueError) as exc:
        return 'Saved. Generating the desktop layout needs attention: ' + str(exc)
    binary = os.environ.get('EWW_BIN', 'eww')
    if not shutil.which(binary):
        return 'Saved. Install EWW to open the desktop dashboard.'
    try:
        result = subprocess.run([str(ROOT / 'launch_dashboard'), '--reload'], capture_output=True, text=True, timeout=40)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 'Saved. The dashboard could not reload: ' + str(exc)
    if result.returncode:
        return 'Saved. Dashboard reload needs attention: ' + result.stderr[-800:]
    return 'Saved and applied. Your space is ready.'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass  # Never log authentication headers or settings.

    def send(self, status, data, mime='application/json; charset=utf-8'):
        body = json.dumps(data, ensure_ascii=False).encode() if not isinstance(data, bytes) else data
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        host = self.headers.get('Host', '')
        expected = f'127.0.0.1:{self.server.server_port}'
        if host not in (expected, f'localhost:{self.server.server_port}'):
            return False
        origin = self.headers.get('Origin')
        if origin and origin not in (f'http://{expected}', f'http://localhost:{self.server.server_port}'):
            return False
        return hmac.compare_digest(self.headers.get('X-Orbit-Token', '').encode(), TOKEN.encode())

    def do_GET(self):
        route = urlsplit(self.path).path
        if route.startswith('/api/'):
            if not self.authorized():
                self.send(403, {'error': 'Session expired. Reopen Customize from Orbit.'})
                return
            try:
                if route == '/api/state':
                    error = ''
                    migration_notes = []
                    try:
                        if CONFIG.exists():
                            p = read()
                        else:
                            p, migration_notes = migrate()
                    except Invalid as exc:
                        p, error = defaults(), str(exc)
                    backups = sorted((x.name for x in BACKUPS.glob('*.json')), reverse=True)
                    self.send(200, {'settings': p, 'defaults': defaults(), 'themes': THEMES, 'error': error,
                                    'revision': revision(), 'backups': backups, 'path': str(CONFIG), 'migration_notes': migration_notes,
                                    'apps': applications(), 'monitors': monitors(), 'eww': bool(shutil.which(os.environ.get('EWW_BIN', 'eww')))})
                elif route == '/api/diagnostics':
                    result = subprocess.run([str(ROOT / 'scripts/dashboard_doctor')], capture_output=True, text=True, timeout=20)
                    self.send(200, {'ok': result.returncode == 0, 'output': result.stdout + result.stderr})
                else:
                    self.send(404, {'error': 'Unknown endpoint'})
            except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                self.send(400, {'error': str(exc)})
            return
        paths = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
        if route not in paths:
            self.send(404, b'Not found', 'text/plain')
            return
        path = STATIC / paths[route]
        self.send(200, path.read_bytes(), mimetypes.guess_type(path)[0] or 'text/plain')

    def do_POST(self):
        if not self.authorized():
            self.send(403, {'error': 'Session expired. Reopen Customize from Orbit.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 8 * 1024 * 1024:
                raise Invalid('Request is empty or too large (maximum 8 MB).')
            self.connection.settimeout(15)
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise Invalid('Expected a JSON object')
            route = urlsplit(self.path).path
            if route in ('/api/save', '/api/reset', '/api/restore'):
                with WRITE_LOCK:
                    if data.get('revision') != revision():
                        self.send(409, {'error': 'Settings changed in another window. Reload before saving.'})
                        return
                    if route == '/api/save':
                        p = save(data['settings'])
                    elif route == '/api/reset':
                        p = save(defaults())
                    else:
                        p = restore(data['name'])
                    message = apply(p)
                    self.send(200, {'settings': p, 'revision': revision(), 'message': message})
            elif route == '/api/import':
                p = validate(data['settings'])
                p['advanced']['enabled'] = False
                self.send(200, {'settings': p})
            elif route == '/api/search':
                query = str(data.get('query', '')).strip()
                if not 2 <= len(query) <= 100:
                    raise Invalid('Enter a city name (2–100 characters).')
                url = 'https://geocoding-api.open-meteo.com/v1/search?' + urlencode({'name': query, 'count': 8, 'language': 'en', 'format': 'json'})
                with urlopen(url, timeout=8) as response:
                    payload = json.loads(response.read(200000))
                if not isinstance(payload, dict) or not isinstance(payload.get('results', []), list):
                    raise Invalid('The location service returned an invalid response. Please try again later.')
                matches = payload.get('results', [])
                self.send(200, {'results': [{'name': ', '.join(str(x[k]) for k in ('name', 'admin1', 'country') if x.get(k)),
                                           'latitude': str(x['latitude']), 'longitude': str(x['longitude'])} for x in matches]})
            elif route == '/api/choose':
                if not shutil.which('zenity'):
                    raise Invalid('Install zenity for a native picker, or type a path / upload an image here.')
                argv = ['zenity', '--file-selection', '--title=Choose for Orbit']
                if data.get('kind') == 'folder':
                    argv.append('--directory')
                result = subprocess.run(argv, capture_output=True, text=True, timeout=120)
                self.send(200, {'path': result.stdout.strip() if result.returncode == 0 else ''})
            elif route == '/api/upload':
                image = base64.b64decode(data['image'], validate=True)
                if len(image) > 5 * 1024 * 1024:
                    raise Invalid('Choose an image smaller than 5 MB.')
                if image.startswith(b'\x89PNG\r\n\x1a\n'):
                    extension = '.png'
                elif image.startswith(b'\xff\xd8\xff'):
                    extension = '.jpg'
                else:
                    raise Invalid('Choose a PNG or JPEG image.')
                target = CONFIG_DIR / 'assets' / (hashlib.sha256(image).hexdigest() + extension)
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('wb') as f:
                    f.write(image)
                os.chmod(target, 0o600)
                self.send(200, {'path': str(target)})
            elif route == '/api/test':
                launch(data['collection'], int(data['index']))
                self.send(200, {'message': 'Shortcut launched using your saved settings.'})
            elif route == '/api/dashboard':
                result = subprocess.run([str(ROOT / 'launch_dashboard'), '--open'], capture_output=True, text=True, timeout=40)
                if result.returncode:
                    raise Invalid(result.stderr[-1200:] or 'Dashboard did not open. Check Diagnostics.')
                self.send(200, {'message': 'Dashboard opened.'})
            elif route == '/api/shutdown':
                self.send(200, {'message': 'Orbit Studio closed.'})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self.send(404, {'error': 'Unknown endpoint'})
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
            self.send(400, {'error': str(exc)})


def main():
    parser = argparse.ArgumentParser(description='Orbit Studio — private local customization')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--stop', action='store_true', help='Close this configuration’s local Studio server')
    args = parser.parse_args()
    os.umask(0o077)
    # One instance per user configuration. A second launch opens the existing URL.
    import fcntl
    url_file = STATE / 'studio-url'
    if args.stop:
        try:
            url = urlsplit(url_file.read_text().strip())
            if url.scheme != 'http' or url.hostname != '127.0.0.1':
                return
            session = parse_qs(url.fragment).get('token', [''])[0]
            request = Request(f'http://{url.netloc}/api/shutdown', data=b'{}', headers={'X-Orbit-Token': session})
            with urlopen(request, timeout=3):
                pass
        except (OSError, ValueError):
            pass
        return
    STATE.mkdir(parents=True, exist_ok=True)
    lock = (STATE / 'studio.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        if url_file.exists():
            open_browser(url_file.read_text().strip(), args.no_browser)
        return
    for port in range(args.port, args.port + 20):
        try:
            server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
            break
        except OSError:
            continue
    else:
        raise SystemExit('No free local port found for Orbit Studio.')
    server.daemon_threads = True
    url = f'http://127.0.0.1:{server.server_port}/#token={TOKEN}'
    atomic(url_file, url)
    open_browser(url, args.no_browser)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        url_file.unlink(missing_ok=True)


def open_browser(url, disabled=False):
    print('Orbit Studio: ' + url, flush=True)
    if not disabled:
        for argv in (['xdg-open', url], ['gio', 'open', url]):
            if shutil.which(argv[0]):
                subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                break


if __name__ == '__main__':
    main()
