# Contributing

## Before submitting a change

Run:

```bash
tests/check.sh
```

When changing the EWW configuration, also test with an installed EWW `0.6.0+` instance on the desktop/session you support.

See README's `smoke_studio.cjs`, `smoke_eww.py`, and `smoke_wayland.py` commands for actual browser, X11, and Wayland checks. The browser test starts its own isolated server and settings; the EWW tests never invoke power actions.

## Design requirements

- Do not add personal absolute paths.
- Treat external applications as optional.
- Keep X11 and Wayland behavior in mind.
- Use GTK-compatible CSS rather than browser-only CSS units.
- Treat preferences as validated data; never add a new path that executes the user settings file.
- Keep Studio usable with keyboard navigation, a narrow viewport, and without optional desktop integrations.
- Keep custom commands behind the explicit Advanced mode and pass user paths as arguments.
- Preserve GPL notices and upstream asset attributions.
- Update documentation and the changelog for user-visible behavior.
