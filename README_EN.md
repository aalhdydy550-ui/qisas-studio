<!-- Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui) -->
<!-- Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE. -->
<!-- Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md. -->
# studio — Unified Story-Video Production Pipeline (brief English)

`studio` is an **orchestration layer only**: it unifies three tools
installed on the same machine into one pipeline for short moral-story
videos (Facebook + YouTube Shorts). It contains no code from any of
the three tools and does not modify them.

## Architecture

```
Story text
   │
   ▼
OmniRoute   — intelligence: hook/title/caption via free models (with fallback)
   │
   ▼
OpenMontage — production: research, script, Piper narration, stock images
   │
   ▼
Concat      — final assembly: editable project + export
   │
   ▼
Vertical 720×1280 video ready to publish
```

| Layer | Tool | License |
|---|---|---|
| Intelligence | [OmniRoute](https://github.com/ChrisCompton/omniroute) | MIT |
| Production | [OpenMontage](https://github.com/OpenMontageInc/OpenMontage) | AGPL-3.0 |
| Assembly | [Concat](https://github.com/jub0t/Concat) | AGPL-3.0 |

## Quick start

```bash
python3 studio.py status
python3 studio.py run --story anza --project anza-part1 \
    --out ~/workspace/videos/studio-test.mp4 --allow-fallback
```

Copy `config.example.yaml` to `config.yaml` to change paths/endpoints.
Never put secrets in config files; the OmniRoute gateway key (if any)
goes through the `OMNIROUTE_API_KEY` environment variable only.

Round 7 (0.1.31) commands: `batch --count N [--source veo|openmontage]`
(dry-run by default; real run only with `--execute`), `publish --platforms
tiktok,instagram` (dry-run prints the payload; real upload untested — no
accounts connected) + `tiktok-auth`/`instagram-auth` (print manual steps),
`analyze --dna --video FILE` (viral-DNA analysis: hook 0–10, pacing,
silence, word density), `balance --cap N` (Veo spend cap, refused in Arabic
before any spend), `scene-plan --story N` (scene plan printed and saved
before spending any credits).

Batches: `batch --count N` is the current batch path — it checks the
Veo balance (120 units per video) and the spend cap before planning,
and is dry-run by default (real run only with `--execute`). `run-queue`
is a legacy compatibility command kept working as-is: it runs ready
stories straight from the queue file, with no balance or cap check.

Platforms: built for Linux (Ubuntu). On Windows, use WSL2 + Ubuntu —
the supported way. On macOS it generally works, but the auto-restore
layer (`setup-env.sh`) is Linux-only: it installs apt packages (such as
ffmpeg, mesa-vulkan-drivers, melt and xvfb) and restores `/usr/local/bin`
links, so on macOS install their equivalents manually (e.g. via Homebrew)
and the auto-restore does not run; `setup.sh` itself has no OS check,
and its python3-missing hint suggests `apt-get` (Debian/Ubuntu).

## Known limits (verified 2026-11-20)

- Concat does not generate video; Veo clips still come from Google Flow.
- The working free keyless path is DuckDuckGo AI Chat via
  `ddgw/gpt-5.4-mini` (verified 2026-11-20: answered in Arabic in
  ~2–11 seconds). The native Pollinations provider now requires a
  real API key (account signup), and g4f-pollinations is out of free
  credits (402). With `--allow-fallback`, `run` uses the hook from
  the ready OpenMontage script and records that in `script-ai.json`.
- Export is slow without a GPU (Concat needs Vulkan; lavapipe via
  `mesa-vulkan-drivers` on headless machines). ffmpeg is faster for
  stitching Veo clips, but Concat keeps the project editable.

See `README.md` (Arabic) for full documentation.

## v0.1.38 — LLM fallback chain + talking-avatar prep

- **LLM fallback chain:** every intelligence call tries providers in
  order (OmniRoute: model then fallback, then Gemini
  `gemini-3-flash-preview` via a safe helper with a surrogate key —
  the raw key never appears in any file, argument, or log); quota
  errors (429/402) put a provider on a 10-minute cooldown that is
  skipped automatically; auth errors (401/403) get no cooldown; total
  failure is an Arabic `llm_all_failed` error. State lives in
  `runs/llm-provider-state.json` (persistent daily counters) with
  `llm-status` and `doctor --llm` (4 separate checks — the main
  doctor count stays 26). The serving model is recorded in six places
  (script, publish-meta, ideas, ab, ab-variants, ab-eval-set) plus
  the provider chain in run records (`llm_chain`).
- **Talking avatar (LongCat) — prep only, no local rendering yet:**
  a LongCat-schema job (`lib/avatar_job.py`: prompt, cond_image,
  cond_audio person1/person2, audio_type para/add, settings,
  audio.kind=narration — validated: image exists, audio ≤300s, para
  needs matching durations ±0.1s, plus a "clean audio only" rule
  that rejects only continuous audio ≥15s with zero silence and
  mean >-30 dB — calibrated on 10 real narration files, all pass
  since they are <15s), a structured 4-slot performance prompt for
  three scene types, hardware profiles (t4x2-int8 default, a100-bf16,
  rtx4090-int8; fp8+int8 rejected together), an audio-performance
  profile (per-second energy curve + silence map + emphasized
  phrases ≥6 dB above the median), and vertical-only aspects
  divisible by 8 (default 720×1280; 720×1092 is the pilot portrait
  input size, not an output size). Wiring: `avatar-job`
  (--validate/--template/--list-profiles), `check --avatar-image`
  (aspect rule in lib/check.py — warning only), and
  `analyze --dna --audio-profile` (profile attached to the report;
  its failure never fails DNA).
- **CI fix:** the workflow installs ffmpeg (and melt best-effort);
  machine-dependent tests skip cleanly when the environment is
  missing, with regression tests proving the skip
  (`tests/test_ci_skips.py`).

## License

This orchestration layer only is licensed under the
**PolyForm Noncommercial License 1.0.0** (see `LICENSE`):
personal and noncommercial use is free.

### Commercial license

Commercial use requires a paid license:
- **Individuals: EGP 1000**
- **Companies: EGP 5000**

**Payment (Vodafone Cash):** send the amount to **01023468196**,
then open an Issue in this repository and attach a screenshot
of the transfer with the license type (individual or company),
and the license file will be sent to you.

The three tools (OmniRoute, OpenMontage, Concat) are independent
projects under their own licenses (see the table above) and are
not covered by this repository's license.

The orchestrated tools (OpenMontage and Concat) are used unmodified,
exactly as released by their authors, and buyers obtain them
themselves from their sources under AGPL-3.0 with all of its rights
(use, study, modification, sharing):
[OpenMontage](https://github.com/OpenMontageInc/OpenMontage) and
[Concat](https://github.com/jub0t/Concat).
