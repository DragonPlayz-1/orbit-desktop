# Release checklist

- Revoke and remove any accidentally exposed credentials.
- Confirm the release tree is being published from `DragonPlayz-1/orbit-desktop`, not the legacy `widgets` repository.
- Start from a clean checkout.
- Run `tests/check.sh`.
- Run `NODE_PATH=/path/to/node_modules node tests/smoke_studio.cjs` with Playwright 1.58.2.
- Run `tests/smoke_eww.py` under Xvfb at the five resolutions in CI.
- Run `tests/smoke_wayland.py` under `dbus-run-session` with headless Sway.
- Verify all scripts are executable in the release tree.
- Verify `eww/dashboard/images` references resolve.
- Test installation with a temporary home directory.
- Test upgrade preservation, backup restore, reset, and uninstall without purge.
- Test invalid JSON, invalid values, and legacy migration without executing legacy commands.
- Test EWW configuration parsing with EWW `0.6.0+`.
- Test X11 and Wayland.
- Test a missing weather configuration.
- Test offline weather with a populated cache.
- Test no music player, MPRIS, and MPD.
- Test launcher open/close races.
- Test confirmation cancellation and successful power action paths without invoking destructive operations in CI.
- Test shortcut paths containing spaces, quotes, shell metacharacters, and missing folders.
- Test local Studio authentication, origin checks, request-size limits, and revision conflicts.
- Review third-party asset licenses.
- Update `CHANGELOG.md` and README support information.

The CI workflow pins the upstream EWW v0.6.0 source archive checksum and Rust
1.76.0, then builds both X11 and Wayland backends. Tests verify all six palettes,
large text, literal user strings, live data polling, empty-card layouts, and
open/close behavior. They tolerate only the known upstream IPC response-deadline
messages; GTK/Yuck and polling diagnostics fail the rendering job.
