"""Bounded, retryable album art cache with a dependable local fallback."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen
import fcntl

sys.dont_write_bytecode = True
from preferences import CACHE, ROOT, read


def supported(data):
    return data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff')


def artwork(backend, player):
    p = read()
    fallback = ROOT / 'images/music.png'
    if not p['music']['artwork']:
        return fallback
    if backend == 'mpd':
        name = subprocess.check_output(['mpc', '-f', '%file%', 'current'], timeout=2, text=True).strip()
        base = Path(p['music']['directory']).expanduser().resolve()
        parent = (base / name).parent.resolve()
        if base not in (parent, *parent.parents):
            return fallback
        for name in ('cover.jpg', 'cover.png', 'folder.jpg', 'folder.png'):
            candidate = parent / name
            if candidate.is_file():
                return candidate
    if backend != 'mpris':
        return fallback
    uri = subprocess.check_output(['playerctl', '-p', player, 'metadata', '--format', '{{mpris:artUrl}}'], timeout=2, text=True).strip()
    parsed = urlsplit(uri)
    if parsed.scheme == 'file' and parsed.netloc in ('', 'localhost'):
        path = Path(unquote(parsed.path))
        if path.is_file():
            with path.open('rb') as f:
                if supported(f.read(16)):
                    return path
    if parsed.scheme not in ('http', 'https'):
        return fallback
    directory = CACHE / 'music'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'art.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return fallback
        key = hashlib.sha256(uri.encode()).hexdigest()
        target = directory / (key + '.image')
        if target.is_file():
            return target
        stamp = directory / (key + '.attempt')
        if stamp.exists() and time.time() - stamp.stat().st_mtime < 60:
            return fallback
        stamp.touch()
        with urlopen(uri, timeout=5) as response:
            if urlsplit(response.url).scheme not in ('http', 'https'):
                return fallback
            data = response.read(5 * 1024 * 1024 + 1)
        if len(data) > 5 * 1024 * 1024 or not supported(data):
            return fallback
        fd, temp = tempfile.mkstemp(dir=directory)
        try:
            with os.fdopen(fd, 'wb') as out:
                out.write(data)
            os.replace(temp, target)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        for old in sorted(directory.glob('*.image'), key=lambda x: x.stat().st_mtime)[:-20]:
            old.unlink()
        for old in directory.glob('*.attempt'):
            if time.time() - old.stat().st_mtime > 86400:
                old.unlink()
        return target


if __name__ == '__main__':
    try:
        print(artwork(sys.argv[1], sys.argv[2]))
    except (OSError, ValueError, subprocess.SubprocessError):
        print(ROOT / 'images/music.png')
