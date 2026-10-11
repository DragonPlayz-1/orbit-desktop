# Security Policy

## Reporting a vulnerability

Please do not open a public issue for credentials, command execution problems, or other security-sensitive defects.

Report security issues privately through the repository owner's GitHub contact options and include:

- affected file and version;
- reproduction steps;
- expected and actual behavior;
- whether the issue requires a particular desktop, compositor, or optional dependency.

## Credential handling

- Never place GitHub tokens, SSH keys, API keys, or passwords in the repository.
- Keep local environment files outside commits.
- Revoke any credential that is accidentally exposed immediately.
- The dashboard does not require a GitHub token.

## Command configuration

Application and update commands are intentionally user-configurable because desktop installations differ. Only place commands you trust in the user-owned configuration file.

## Orbit Studio

Orbit Studio binds to loopback only, uses a random per-session token, rejects unexpected origins and Host headers, does not log request bodies, limits uploads and request sizes, and applies optimistic revision checks before writes. Close the Studio process when you are finished with an unattended session.

Settings are JSON data. The legacy shell configuration is parsed as assignment text during migration and is never sourced or executed.
