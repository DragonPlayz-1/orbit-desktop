# Configuration reference

The user settings file is:

```text
${XDG_CONFIG_HOME:-$HOME/.config}/eww-dashboard/settings.json
```

Use Orbit Studio (`launch_dashboard --settings`) for normal changes. The JSON file is versioned, validated, atomically written, backed up, and never executed as shell code.

The older `dashboard.conf` file is supported only as a legacy import source. Custom commands from that file are imported disabled for review.

## Weather

Search for a location in Studio, or set both values in the weather editor before weather requests are made:

```json
{"place":"New Delhi","latitude":"28.6139","longitude":"77.2090","unit":"metric","refresh":600}
```

This is the `weather` object inside settings, not a complete settings file. Valid units are `metric` and `imperial`. Clear both coordinates to disable weather. Invalid or incomplete values are rejected with a field-specific error before saving.

## Appearance and layout

Studio controls presets, custom accent colors, light/dark mode, contrast, reduced motion, font size, corner radius, opacity, background image, density, column count, monitor, card visibility, labels, and order.

## Commands

Application selection uses installed desktop entries or safe built-in launchers. Arbitrary shell commands are only available in Advanced mode and are disabled by default when migrated or imported.

## Monitor

Use a numeric monitor index or a compositor output name:

Choose one of Studio's detected displays, or type `0`, `DP-1`, or `<primary>` in the Monitor field. A disconnected output causes a clear launch failure; choose a connected display to recover. Column count is a maximum: when display discovery is available, Orbit reduces it to keep text readable. Content scrolls vertically.

Studio applies validated changes automatically. If you edit JSON manually, run `dashboard_config --validate` before restarting.

## Recovery

Every existing settings file is backed up before a successful save. Use **Backups & health** in Studio to restore one of the 20 most recent versions, reset to defaults, export a portable JSON copy, or run diagnostics.

Exports contain preferences and image paths; uploaded files are not embedded. Re-select images and folders after importing on another machine. Import validates the entire document and disables Advanced commands until you explicitly re-enable them.

## Paths and overrides

- `DASHBOARD_CONFIG_HOME`: settings directory (default `~/.config/eww-dashboard`).
- `DASHBOARD_SETTINGS_FILE`: override the JSON file location.
- `DASHBOARD_CONFIG_FILE`: legacy shell-assignment import file, not the new JSON file.
- `EWW_BIN`: custom EWW executable; shared by installer and runtime.
- XDG config, cache, data, and state paths are respected.

Generated EWW files live in `~/.cache/eww-dashboard/runtime`. Edit preferences or source templates rather than generated files.
