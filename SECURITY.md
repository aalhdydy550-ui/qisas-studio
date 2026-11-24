<!-- Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui) -->
<!-- Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE. -->
<!-- Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md. -->
# Security Policy — qisas-studio

> ملخص عربي: إن وجدت ثغرة أمنية فلا تفتح Issue عامة — بلّغ عنها سرًا
> عبر «Report a vulnerability» في GitHub (تنبيه أمني خاص) وسيرد عليك
> المالك. لا ترفق أسرارًا حقيقية في بلاغك أبدًا.

## Supported versions

Only the latest released version is supported with security fixes.
Check the current version with:

```bash
python3 studio.py version
```

and see the latest entry in [CHANGELOG.md](CHANGELOG.md). Older
versions may still work, but they do not receive security fixes —
please upgrade before reporting.

## How to report a vulnerability

**Do not open a public issue for a security vulnerability.**

Report it privately via GitHub's **"Report a vulnerability"** button
(Security tab → "Report a vulnerability") on this repository. That
creates a private security advisory visible only to the maintainers.

In your report, please include:

1. A clear description of the vulnerability and what an attacker could
   do with it.
2. The exact steps to reproduce it (commands, inputs, expected vs.
   actual behavior).
3. The version you tested (`python3 studio.py version`) and your
   environment (OS, Python version).
4. Your assessment of the impact, if you have one.

What you can expect:

- An acknowledgement within a few days.
- A fix (or a mitigation) in the next release, plus a note in
  [CHANGELOG.md](CHANGELOG.md) crediting you if you wish.
- No public disclosure of the details until a fix is available.

## What NOT to include in a report

- **Never include real secrets**: no API keys, tokens, passwords,
  `.env` files, `config.yaml`, `client_secrets.json`, or
  `youtube-token.json`. Reproduce the issue with fake data only.
- **Never include real customer data**: no real WhatsApp numbers, no
  real client orders, no real published videos or queue files. Use test
  data.
- **Do not test on live accounts**: do not probe the project's real
  Facebook page, YouTube channel, or client-order page. Reproduce
  locally.

## Scope

**In scope** — the code in this repository:

- Command injection, path traversal, and shell escaping in `studio.py`
  and `lib/` (all subprocess calls must be argument lists, no
  `shell=True`).
- Secret leakage: secrets printed to logs, written to `runs/`, or
  included in manifests, thumbnails, or uploaded files.
- Authentication/authorization on the client-order page and the
  OpenCut bridge (`Bearer` only, signed media links, asset-folder
  limits).
- Input handling of story text, titles, and ASS captions (ASS-tag and
  shell injection via story text).
- Dependency issues in the tools this project installs or invokes.

**Out of scope:**

- The three orchestrated tools themselves (OmniRoute, OpenMontage,
  Concat) — report issues in their own repositories. This project only
  coordinates them without modifying them.
- Google Flow / Veo, Facebook, YouTube, TikTok, Instagram, or any
  third-party service — report to the service owner.
- Social engineering, physical access, or attacks that require the
  victim to run untrusted code on their own machine.
- Reports about missing security headers on a page you do not own, or
  about theoretical issues with no reproducible impact.
- Automated scanner output with no verified, reproducible finding.

## Security notes for users and contributors

- Secrets (`client_secrets.json`, `youtube-token.json`, `.env`,
  token files) live in 600-permission files covered by `.gitignore`.
  Before any upload to GitHub, verify:
  `git check-ignore client_secrets.json youtube-token.json config.yaml .env`
  — all of them must show as ignored. Uploading via the Contents API
  bypasses `.gitignore`, so this manual check is mandatory.
- The OmniRoute server binds to `127.0.0.1:20128` only (loopback) with
  `REQUIRE_API_KEY=true` for permanent use; run it for testing only
  and stop it afterwards (`omniroute stop`).
- The OpenCut bridge accepts `Bearer` tokens only — never `?token=` in
  a URL — and its signed media links expire after 10 minutes.

## Past audits

Defensive penetration tests were run on this project in November 2026
(v0.1.22, v0.1.25–0.1.28). Their findings and fixes are recorded in
[CHANGELOG.md](CHANGELOG.md) and in `SECURITY-AUDIT-2026-11-21.md`.
