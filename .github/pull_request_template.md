## What changed?

<!-- Describe the user-visible result and the reason for the change. -->

## Verification

- [ ] `tests/check.sh`
- [ ] Browser Studio smoke test (when Studio changed)
- [ ] X11 or Wayland EWW smoke test (when dashboard/runtime changed)
- [ ] Documentation and changelog updated when behavior changed

## Release hygiene

- [ ] No secrets, personal absolute paths, generated caches, or temporary files are included.
- [ ] New commands treat user settings as validated data and keep custom shell execution explicit.
- [ ] Third-party assets and licenses are documented.
