# Getting Started — From Install to Your First Video

New-user guide for **qisas-studio**: a studio that produces short Arabic
story videos (Facebook + YouTube Shorts) with one command. Arabic version:
[`getting-started.md`](getting-started.md).

> **Expected time:** ~15 minutes from install to your first demo video.
> **Cost:** $0 on the free path — no keys, no credits.

## 1) What is this project?

`studio` is one orchestration layer that unifies three tools installed on
your machine:

| Layer | Tool | Role |
|---|---|---|
| Intelligence | OmniRoute | Hook, title, and caption via free models |
| Production | OpenMontage | Script, narration, images, assembly |
| Assembly | Concat | Editable project + video export |

Result: a vertical **720×1280** video, **40–60 seconds** long, Arabic
narration in a male voice (Piper), with on-screen writing synced to the
speech **below the picture only**.

## 2) Requirements

- **Linux (Ubuntu)** — on Windows use WSL2 + Ubuntu (the supported way).
  On macOS it generally works, but the auto-restore layer is Linux-only.
- Python 3 and ffmpeg (the installer checks them and prints an honest
  PASS/FAIL per check).
- No API key is needed to start: the free path works with no keys.

## 3) Install

```bash
# From the studio folder:
bash setup.sh
```

The installer checks everything — tools, models, fonts, logo, server —
and creates `config.yaml` from `config.example.yaml` if missing. It is
safe to re-run at any time.

Then check status only (no repairs):

```bash
python3 studio.py doctor
```

You should see **26/26** checks passing. If a check fails, read its
message — it tells you exactly what is missing and how to fix it.

## 4) Your first video — the built-in demo

```bash
python3 studio.py run --demo
```

This builds a real vertical 720×1280 video in ~1 minute on the free path
only (Piper + generated backgrounds + logo) — no keys, no credits, no
internet. Find the output file in the folder the command prints (under
`runs/` or the path you gave).

Verify the video:

```bash
python3 studio.py check --video <path-to-video>
```

## 5) Your first video from a real story

Ready-made example — the "goat" story from a ready OpenMontage project:

```bash
python3 studio.py run --story anza --project anza-part1 \
    --out ~/workspace/videos/studio-test.mp4 --allow-fallback
```

Every run creates a folder in `runs/<story>-<time>/` containing:
`script-ai.json` (hook and caption), `manifest.json` (assets),
`assets/` (images + narration + writing), and `run-log.json`
(steps and timings).

Dry-run mode prints the steps without executing:

```bash
python3 studio.py run --story anza --project anza-part1 \
    --out ~/workspace/videos/out.mp4 --dry-run
```

## 6) Thumbnail

```bash
python3 studio.py thumbnail --video ~/workspace/videos/studio-test.mp4 \
    --hook "She threw me out at midnight… and a year later she kissed my hand!"
```

## 7) Publishing — try it first without publishing anything

```bash
python3 studio.py publish --video ~/workspace/videos/studio-test.mp4 \
    --title "He sold his cow and shared the seeds | Short story" --dry-run
```

`--dry-run` shows the exact payload before anything goes live. Real
publishing: Facebook works directly via the connected `facebook-cli`;
YouTube needs a one-time OAuth setup — see
[`README-AR.md`](../README-AR.md), section «النشر على يوتيوب»
(Arabic), or ask in an issue.

## 8) The daily line — queue and batches

Add a story to the queue in one line:

```bash
python3 studio.py queue add --title "Story title" --text-file ~/workspace/story.txt
```

Print today's plan with no spend:

```bash
python3 studio.py daily --dry-run
```

A batch (dry-run by default, prints the plan; real run only with
`--execute`):

```bash
python3 studio.py batch --count 3 --source openmontage
```

## 9) Commands you will use every day

| Command | What it does |
|---|---|
| `python3 studio.py status` | Server and binaries status |
| `python3 studio.py doctor` | 26 system checks |
| `python3 studio.py doctor --llm` | Status of the five LLM legs |
| `python3 studio.py llm-status` | The legs in order, with the date |
| `python3 studio.py version` | Version and remote status |
| `python3 studio.py help-ar` | Arabic help for every command |
| `python3 studio.py analyze --dna --video <file>` | Viral-DNA analysis of a video |
| `python3 studio.py scene-plan --story 4` | Scene plan before spending any credits |
| `python3 studio.py balance --cap 600` | Veo spend cap |

## 10) Golden rules for new users

1. **Never put keys in config files.** An OmniRoute gateway key (if any)
   goes through the `OMNIROUTE_API_KEY` environment variable only.
2. **Try `--dry-run` before any real run** — especially `publish`,
   `batch`, and `daily`.
3. **On-screen writing goes below only** — never any text at the top;
   the narrator is always a man; the vertical video is 40–60 seconds.
4. **Do not touch the real queue or published videos in your
   experiments** — test data only.
5. Before any upload to GitHub, verify:
   `git check-ignore client_secrets.json youtube-token.json config.yaml .env`
   — all of them must show as ignored.

## 11) Troubleshooting

| Problem | Fix |
|---|---|
| "omniroute command not found in PATH" | `npm install -g omniroute`, then `omniroute serve --no-open --daemon --port 20128` |
| "Server is not responding" | Start the server with the command above; verify with `python3 studio.py status`; stop it afterwards with `omniroute stop` |
| "No run with this ID" | Run `produce` first (or a full `run`) before `assemble` |
| Tight memory | Export needs the machine idle; do not run an APK build or another render in parallel |

## 12) Where to go next

- Full reference: [`README-AR.md`](../README-AR.md) (Arabic) and
  [`README.md`](../README.md) (English gateway)
- Change log: [`CHANGELOG.md`](../CHANGELOG.md)
- Example commands and expected output: [`examples/`](../examples/)
- Want to contribute? [`CONTRIBUTING.md`](../CONTRIBUTING.md)
- Found a security issue? [`SECURITY.md`](../SECURITY.md) — report it
  privately, never in a public issue.
- A question? Open an issue from the "Question" template
  (`.github/ISSUE_TEMPLATE/question.md`).
