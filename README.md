<!-- Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui) -->
<!-- Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE. -->
<!-- Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md. -->
# studio — Unified Story-Video Production Pipeline

**One command turns a short story into a vertical video ready to publish on
Facebook and YouTube Shorts.**

> ⭐ **If this project saves you time or money, please star it on GitHub** —
> one click, and it helps others find it.

`studio` is an **orchestration layer only**: it unifies three tools installed
on the same machine into a single pipeline for short Arabic moral-story
videos. It contains no code from any of the three tools and does not modify
them.

> **العربية أولًا — Arabic first.** The project, its interface, and its main
> documentation are Arabic. This file is the English gateway for new users.
> The full Arabic README is [`README-AR.md`](README-AR.md).

---

## What it does

```
Story text
   │
   ▼
OmniRoute   — intelligence: hook / title / caption via free models (with fallback)
   │
   ▼
OpenMontage — production: research, script, Piper narration, stock images
   │
   ▼
Concat      — final assembly: a real, editable project + export
   │
   ▼
Vertical 720×1280 video ready to publish
```

| Layer | Tool | Role | License |
|---|---|---|---|
| Intelligence | [OmniRoute](https://github.com/ChrisCompton/omniroute) | OpenAI-compatible model gateway; hook, title, caption generation | MIT |
| Production | [OpenMontage](https://github.com/OpenMontageInc/OpenMontage) | Agent pipelines: script, narration, images, Remotion assembly | AGPL-3.0 |
| Assembly | [Concat](https://github.com/jub0t/Concat) | Local headless video editor with an MCP server; editable project + export | AGPL-3.0 |

## Who it is for

- **Arabic story-page owners** who publish short moral stories (40–60 s,
  vertical 9:16) twice a day on Facebook and YouTube Shorts.
- **Anyone who wants a $0 daily video line**: the free path (Piper narration +
  stock images + local assembly) costs nothing per video.
- **Developers** who want a tested, self-healing CLI pipeline they can extend
  (see [CONTRIBUTING.md](CONTRIBUTING.md)).

## Highlights (v0.1.40)

**Production — from text to a finished video**
- One command (`python3 studio.py run`) turns a story into a 720×1280
  vertical video for Facebook and YouTube Shorts.
- On-demand generation: any user describes a video and the system builds it
  end-to-end (like Flow) — a "request a video" page, a `client-run` command,
  and a watcher that checks for new orders every 15 minutes.
- AI hook / title / caption from free models (DuckDuckGo AI via OmniRoute),
  with an automatic fallback chain:
  `ddgw/gpt-5.4-mini` → `groq/openai/gpt-oss-120b` → `gemini-3.1-flash-lite` →
  `gemini-3-flash-preview` → `ollama/qwen2.5:7b` — see `llm-status`.
- Arabic narration in a fixed male voice (Piper, `ar_JO-kareem-medium`),
  with on-screen writing synced phrase-by-phrase to the speech (ASS files),
  **always below the picture — never at the top**.
- A thumbnail for every video (hook text + page logo), 3 quote cards per
  story, and a weekly long video (8–12 min, horizontal 1280×720) built
  automatically from the week's published stories — no Veo credits.
- 4 assembly backends: Concat (editable project, default), headless-editor
  (fastest, no Vulkan), MLT (`.mlt` timeline that opens in Kdenlive/Shotcut),
  OpenReel (accepts projects from the OpenReel editor).

**Publishing and growth**
- One publish command (`publish`): one video to Facebook (Page Reel) and
  YouTube (Data API v3), with `--dry-run` showing the exact payload first.
- A proven post format: shocking hook in the first 2 seconds, the moral in
  the first comment, a puzzling closing question, a fixed hashtag pack.
- Real performance analysis (`analyze`): the last published video with real
  numbers from Facebook and YouTube side by side — never invented numbers —
  plus improvement suggestions derived from those numbers.

**Quality and trust**
- **1524/1524 automated tests green** (v0.1.40), `doctor` 26/26 checks,
  CI on GitHub.
- A provenance manifest (`<video>.manifest.json`) with every video: title,
  hook, story, moral, source, scenes, word-timed phrases, sha256 fingerprint.
- A secret-leak guard (`lib/secret_guard.py`) scans the tree before any
  upload; secrets live in 600-permission files covered by `.gitignore`.
- Self-healing: the system reinstalls its own tools and service file after
  any machine restart, with no manual step.

**Earning**
- A ready client-order system: a "request a video" page — the client writes
  a description and the system generates the video automatically. The first
  30 days are free for each new client, with no limit on the number of
  orders; payment is required after that.
- Free-API-key tooling (`studio/free-keys/`): catalogue and safe setup for
  free Groq, OpenRouter, and HuggingFace keys.

**Independent comparison (2026-11-23): qisas-studio ranked 1st, 9.0/10** —
the only project covering the full daily Arabic line (generation + assembly +
publishing + scheduling + client orders + Arabic). Nearest rival
MoneyPrinterTurbo scored 7.0, AutoContent.Live 5.5. Full comparison (Arabic):
`~/workspace/comparison-2026-11-23/COMPARISON-AR.md` (outside this repo).

## Quick start

```bash
# 1) One installer checks everything (safe to re-run)
bash setup.sh
# ...or check status only (no repairs):
python3 studio.py doctor

# 2) A real built-in demo video — vertical 720×1280 in ~1 minute,
#    free path only (Piper + generated backgrounds + logo).
#    No keys, no credits, no internet.
python3 studio.py run --demo

# 3) The full pipeline for a story (example: the goat, from a ready
#    OpenMontage project)
python3 studio.py run --story anza --project anza-part1 \
    --out ~/workspace/videos/studio-test.mp4 --allow-fallback

# 4) Publish (dry-run shows the exact payload before anything goes live)
python3 studio.py publish --video ~/workspace/videos/demo-*.mp4 \
    --title "He sold his cow and shared the seeds | Short story" --dry-run
```

New here? Follow **[docs/getting-started.md](docs/getting-started.md)**
(also in English: [docs/getting-started-en.md](docs/getting-started-en.md)) —
from install to your first video, step by step.

More commands and the full reference live in the Arabic README:
[`README-AR.md`](README-AR.md) — including the daily queue, batches,
long video, thumbnails, `analyze`, `batch`, `scene-plan`, `balance`,
and troubleshooting.

## Requirements

- **Linux (Ubuntu)** — built for it. On Windows use WSL2 + Ubuntu (the
  supported way). On macOS it generally works, but the auto-restore layer
  (`setup-env.sh`) is Linux-only: install its equivalents manually
  (e.g. via Homebrew) and the auto-restore will not run.
- Python 3, ffmpeg, and the three orchestrated tools (the installer checks
  them all and reports PASS/FAIL honestly per check).
- Never put secrets in config files: copy `config.example.yaml` to
  `config.yaml` to change paths/endpoints; an OmniRoute gateway key (if any)
  goes through the `OMNIROUTE_API_KEY` environment variable only.

## Known limits (verified)

- **Concat does not generate video** — it is an assembly editor only. Veo
  clips still come from Google Flow (Veo 3.1); OpenMontage images come from
  stock.
- **Free LLM path that works**: DuckDuckGo AI Chat via `ddgw/gpt-5.4-mini`
  (verified 2026-11-20: Arabic reply in ~5 s). Pollinations now needs a real
  API key; `g4f-pollinations` has exhausted its free quota (402).
- **Slow export without a GPU**: Concat needs Vulkan; on a headless machine
  `mesa-vulkan-drivers` (lavapipe) is required. Exporting 55 s took ~119 s.
  The `headless` and `mlt` backends are faster on CPU-only machines.
- **The machine is small** (1.5 CPU units, ~6 GB RAM): steps run one after
  another, not in parallel, and no servers are left running when done.

## Project structure

```
studio/
├── studio.py            # Entry point (CLI)
├── config.example.yaml  # Sample settings (no secrets)
├── lib/                 # Pipeline stages (omniroute / openmontage / concat / ...)
├── tests/               # 1896 automated tests (standard library only)
├── .github/workflows/
│   └── ci.yml           # py_compile + tests on every push
├── .github/
│   ├── ISSUE_TEMPLATE/  # bug report / feature request / question
│   └── pull_request_template.md
├── docs/
│   ├── getting-started.md     # New-user guide (Arabic)
│   └── getting-started-en.md  # New-user guide (English)
├── examples/            # Example commands + expected output (text only)
├── runs/                # Run outputs (excluded from publishing)
├── README.md            # This file (English gateway)
├── README-AR.md         # Full README (Arabic)
├── CHANGELOG.md         # Change log
├── FIXES.md             # Fix log from the 2026-11-20 review (v0.1.1)
├── SUGGESTIONS.md       # Future ideas (not implemented)
├── THIRD-PARTY-NOTICES.md
└── LICENSE              # PolyForm Noncommercial 1.0.0 (this layer only)
```

## Contributing

Contributions are welcome — bug reports, feature requests, testing (no code
needed), and pull requests. Please read
**[CONTRIBUTING.md](CONTRIBUTING.md)** first: it explains how to report a
bug, propose a feature, send a PR, and the rules that keep the full test
suite green. The short version:

```bash
python3 -m unittest discover -s tests   # the full suite must stay green
python3 studio.py doctor                # system checks
python3 studio.py run --demo            # try the demo
```

## Security

If you find a security vulnerability, **do not open a public issue**.
Report it privately via GitHub's **"Report a vulnerability"** (private
security advisory) on this repository. Details:
**[SECURITY.md](SECURITY.md)**.

## Code of conduct

Be kind, be concrete, and respect the people behind the stories.
Full text: **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)**.

## License

The `studio` orchestration layer (the code in this repository only) is
licensed under **PolyForm Noncommercial 1.0.0** (see [`LICENSE`](LICENSE)):
personal and non-commercial use is free. Third-party notices (the
orchestrated tools and re-implemented logic) are in
[`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md).

**No profiting from copies:** selling, renting, or commercially using
copies or forks of this software is prohibited without a paid commercial
license. Cloning for personal, non-commercial use is free.

### Commercial license

Commercial use needs a paid license:
- **Individuals: 1000 EGP**
- **Companies: 5000 EGP**

**Payment (Vodafone Cash):** transfer the amount to **01023468196**, then
open an Issue in this repository and attach a screenshot of the transfer
with the license type (individual or company), and the license file will
be sent to you.

### Free trial (30 days)

Every new user gets a **30-day free trial for commercial use**, counted
from the first run (`python3 studio.py license` shows the status). After
30 days, the production commands stop with a payment reminder until a
commercial license is activated. Personal non-commercial use stays free
forever: run with `--noncommercial` (before the command) to declare it,
e.g. `python3 studio.py --noncommercial run --demo`. The studio owner's
own install is exempt as licensor.

### Star gate (v0.1.48)

Before the production commands (`run`, `produce`, `assemble`, `publish`,
`batch`, `daily`, `long-video`, `client-run`) the studio checks once that
you starred this repository on GitHub — via the public GitHub API, no
token, and the positive result is cached locally (`~/.qisas-studio/star.json`)
so it is asked only once. `doctor`, `license`, `--help`, and `--dry-run`
are never gated, and the studio owner's own install is exempt as licensor.
Be honest about what it does **not** do: it cannot prevent cloning — `git
clone` works without any account. If GitHub is unreachable with no cached
result, it warns and lets the run proceed (fail-open, documented in
`lib/star_gate.py`), and re-checks on the next online run. Tests can
disable it with `QISAS_SKIP_STAR_CHECK=1` (tests only).

### On-demand video requests

`python3 studio.py request "a topic or a full story"` — a full story text
is used as-is; a short topic is turned into a story by the LLM chain
(ddgw ← groq ← gemini-3.1-flash-lite ← gemini-3-flash-preview ← ollama)
in the page's style, saved to the queue, and produced with the current
pipeline. Without a ready OpenMontage project the request ends honestly
as `queued` (story saved, number known) — building a project from free
text is not supported yet.

### Story index (local, optional — v0.1.48)

`queue add` refuses a semantically near-duplicate story (cosine ≥ 0.70)
instead of adding it, and `analyze` / `ab` show the «nearest previous
video» when one exists. The index is a local-only Qdrant collection
(`runs/story-index/`, no server, no Docker, no cloud) with embeddings
from local Ollama (`POST /api/embed`, default model `bge-m3`, 1024 dims).
`qdrant-client` is an optional dependency: install it with
`pip install qdrant-client` to enable the index; without it (or without
Ollama) every command works exactly as before (fail-open). Threshold
calibration (live, bge-m3): near-duplicates 0.75–0.80, different topics
0.49–0.53, unrelated 0.28–0.42.

### Second narrator voice (optional)

`--voice supertonic-M1` on `init`, `long-video`, and `long-narration`
adds Supertonic M1 as an optional second male narrator (A/B test: WER
0.078 / CER 0.021 / F0 131 Hz — the clearest). **Piper stays the default
always.** Supertonic normalizes `؛`→`،` and spells numbers as words
automatically; its license (`lib/supertonic/LICENSE.txt`, OpenRAIL-M)
requires the line «صوت مولّد بالذكاء الاصطناعي» in the description of
any video using it — `publish` appends it automatically (detected from
the video manifest, or via `--ai-voice`). To use the voice, create its
venv once: `python3 -m venv .venv-supertonic &&
.venv-supertonic/bin/pip install supertonic` (the model downloads once
to `~/.cache/supertonic3`).

### Real motion in long videos

`long-video` now moves its scenes with real generated motion clips
instead of Ken Burns: `--motion clips` (the default) takes motion clips
from a manifest (`--motion-manifest manifest.json|csv`,
`--motion-dir dir/` with the generated mp4s) — take `a` first, then the
opening of take `b` (takes are independent, both from the same first
frame); a missing `b` freezes the last frame of `a`. Any chapter without
a clip falls back to a still image with no Ken Burns at all, with a clear
warning in the log and run record. `--motion still` uses still images
only; `--motion kenburns` keeps the old slow zoom/pan — explicit opt-in
only, never the default. `--motion youtube-long` is like `clips` for
resolved motion clips, but its still-image fallback cuts every 2.5s
instead of 5s (the fast-cut rhythm measured in long YouTube story
videos — see `~/workspace/flow-eval/youtube-motion/REPORT-AR.md`) and
never uses Ken Burns. Since 0.1.46 the time left over after the motion
clips in a chapter is also split into alternating stills at the mode's
pace (2.5s in youtube-long, 5s in clips) instead of one long frozen
image. The chapters file accepts `motion`,
`motion_manifest`, `motion_dir`, and per-chapter `motion_clips`.

### Optional assets (v0.1.50; music removed in 0.1.51)

`assemble` accepts opt-in audio/visual assets from a local assets
folder — sound effects at chosen timestamps, and film overlays that
never touch the caption band (the bottom 200 px at 720×1280 stay
structurally untouched):

```
python3 studio.py assemble --run <RUN_ID> --out out.mp4 \
    --sfx impact@5.0 --overlay burn
```

- `--sfx NAME@SECONDS` (repeatable), `--overlay burn|grain`
  (repeatable), `--assets-dir PATH` (overrides `QISAS_ASSETS_DIR`
  and the default folder).
- The assets live **outside** the repo in
  `~/workspace/studio-work/drive-assets/adapted/` (Mixkit Free License
  + one Freesound CC0 file, documented in `ADAPTED-AR.md`) — they are
  never copied into the repo and never shipped with studio copies, per
  their license. A missing assets folder or a missing asset is skipped
  with a warning, never an error.
- Without these flags nothing changes: the daily publish line renders
  exactly as before. Making assets a default is a separate decision
  after the demo is watched and heard.

### Support the project

If the project saved you time or money, you can support it monthly via
[GitHub Sponsors](https://github.com/sponsors/aalhdydy550-ui) — the
«Sponsor» button at the top of the page. Support funds new features; it
does not change the license: personal use stays free.

> Note: the three tools (OmniRoute, OpenMontage, Concat) are independent
> projects with their own licenses (see the architecture table above) and
> are not covered by this repository's license.
>
> The orchestrated tools (OpenMontage and Concat) are used unmodified, as
> released by their owners, and the buyer obtains them directly from their
> sources under AGPL-3.0 with all its rights (use, study, modify, share):
> [OpenMontage](https://github.com/OpenMontageInc/OpenMontage) and
> [Concat](https://github.com/jub0t/Concat).

## Changelog

See [CHANGELOG.md](CHANGELOG.md) — latest: **0.1.46 (2026-11-24)**:
frozen-image gap fix — the time left over after motion clips in a
chapter is split into alternating stills at the mode's pace (2.5s in
youtube-long, 5s in clips) instead of one long frozen image. Full test
suite **1903/1903**, `doctor` 28/28.
