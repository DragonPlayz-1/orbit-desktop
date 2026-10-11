# Integrations

## Music

Orbit tries MPRIS through `playerctl` first. If no MPRIS player is available, it falls back to MPD through `mpc`.

Set a preferred player in Studio when multiple MPRIS players are active:

For example, enter `spotify` in **Music & system → Preferred MPRIS player**. Automatic selection prefers a playing player over a paused one. Seeking works with mouse-wheel up/down and uses your configured seek step.

Orbit keeps album art local, limits remote artwork to 5 MB, accepts PNG/JPEG only, caches at most 20 covers, and falls back to the bundled image when an art provider fails.

## Volume

Volume detection tries `wpctl`, `pactl`, `pamixer`, and `amixer` in that order, continuing to the next backend if a tool is installed but unavailable. External calls have timeouts. No working audio backend displays zero volume.

## Links and folders

The dashboard prefers `xdg-open`, then `gio open`. Studio stores URLs after validating the scheme and passes folder paths as arguments rather than interpolating them into shell source.

## Updates

Update detection is informational and cached for 15 minutes. The button only launches a command when Advanced mode has explicitly enabled one. This prevents a dashboard click from silently running a distribution-specific package upgrade.

Detection supports Arch's `checkupdates`, `apt list --upgradable` (using the system's existing package indexes), and Flatpak. Fedora users can configure their own update command; automatic DNF update counting is not implemented.

## Weather

Weather uses Open-Meteo without an API key. City search uses the Open-Meteo geocoding endpoint only when the user requests it. A successful reading is kept offline; a first-run offline dashboard shows a clear unavailable state and never blocks startup.
