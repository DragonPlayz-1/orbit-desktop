# Changelog

## Unreleased

## 0.1.0 — 2026-10-11

- Reworked the dashboard into the Orbit Dashboard product identity.
- Added portable user configuration and XDG-aware runtime paths.
- Added explicit weather configuration with a safe not-configured state.
- Added MPRIS-first and MPD-fallback music control.
- Added confirmation-protected power actions.
- Replaced machine-specific application and session assumptions with detection and overrides.
- Hardened launcher state, weather caching, metrics, installation, and diagnostics.
- Added static checks and release hygiene documentation.
- Accept EWW's upstream `v0.6.0` CLI label (`0.5.0`) in installation and runtime checks, with explicit diagnostics and version-gate regression checks.
- Added Orbit Studio, a private browser-based customization workspace for non-coders.
- Added schema-validated JSON preferences, legacy migration, atomic saves, automatic backups, restore/reset, responsive layout controls, curated themes, application selection, city search, import/export, and diagnostics.
- Reworked the runtime around a generated single-window dashboard with responsive cards, safe argument-based shortcuts, bounded network/cache behavior, real failure-path tests, and EWW/Xvfb rendering verification.
