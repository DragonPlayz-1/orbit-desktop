#!/usr/bin/env python3
"""Run the EWW integration matrix on a private headless Sway compositor."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

with tempfile.TemporaryDirectory(prefix='orbit-wayland-', dir=os.environ.get('ORBIT_TEST_TMP')) as temp:
    root = Path(temp)
    runtime = root / 'runtime'
    runtime.mkdir(mode=0o700)
    config = root / 'sway.conf'
    config.write_text('output HEADLESS-1 resolution 1920x1080 position 0 0\noutput HEADLESS-2 resolution 1280x720 position 1920 0\n')
    env = dict(os.environ, XDG_RUNTIME_DIR=str(runtime), WLR_BACKENDS='headless', WLR_RENDERER='pixman',
               WLR_LIBINPUT_NO_DEVICES='1', WLR_HEADLESS_OUTPUTS='2', ORBIT_TEST_MONITOR='1')
    env.pop('DISPLAY', None)
    with (root / 'sway.log').open('w') as log:
        compositor = subprocess.Popen(['sway', '-c', str(config)], env=env, stdout=log, stderr=log)
    try:
        for _ in range(100):
            sockets = [p for p in runtime.glob('wayland-*') if not p.name.endswith('.lock')]
            ipc = list(runtime.glob('sway-ipc.*.sock'))
            if sockets and ipc:
                break
            if compositor.poll() is not None:
                raise RuntimeError((root / 'sway.log').read_text())
            time.sleep(.1)
        else:
            raise RuntimeError('Headless compositor did not start')
        env.update(WAYLAND_DISPLAY=sockets[0].name, SWAYSOCK=str(ipc[0]))
        subprocess.run([sys.executable, str(Path(__file__).with_name('smoke_eww.py'))], env=env, check=True, timeout=180)
    finally:
        compositor.terminate()
        compositor.wait(timeout=10)
