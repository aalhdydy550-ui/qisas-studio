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
