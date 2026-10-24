# History Briefed

Builds each History Briefed Short from a single episode file: narration, visuals, the fixed outro, thumbnail, title, tags, description and a posting slot (Mon/Wed/Fri, 4:00 PM Sydney time).

Every video follows the same shape:

`hook -> body scenes -> "Subscribe for more stories like this, and comment what I should brief next." -> iconic image over "History doesn't disappear... it just gets briefed."`

Each scene is voiced separately, so image timing follows the real narration. Every Short must be at least 20 seconds (`video.min_seconds` in `config.yaml`).

## Repo layout
| Path | What it is |
|---|---|
| `episodes/*.json` | One file per video: script, image prompts, title, description, tags, thumbnail text |
| `config.yaml` | Voice, image provider, schedule, outro text, video settings |
| `history_briefed/` | The builder code |
| `assets/` | `unique_outro_vertical.png`, `unique_outro_horizontal.png` (the iconic outro image) |
| `.github/workflows/build.yml` | One-click cloud build ("Build Shorts") |
| `videos/` | Finished renders, created by the workflow (public links for Buffer) |
| `build/` | Local render output (not committed) |

## Option A: build in GitHub (no install)
1. Go to **Actions -> Build Shorts -> Run workflow**.
2. Type an episode id (for example `01-emu-war`) or leave it empty to build everything.
3. When it finishes, the video, thumbnail, captions and `queue.json` are committed to `videos/`.

The first run downloads the voice model (a few hundred MB, then cached).

## Option B: build on your own computer
```bash
pip install -r requirements.txt
sudo apt install ffmpeg            # or: brew install ffmpeg
python -m history_briefed setup    # downloads the Kokoro voice model
python -m history_briefed doctor   # checks everything is in place
python -m history_briefed build 01-emu-war
```

## Commands
```bash
python -m history_briefed list              # episodes and their posting slots
python -m history_briefed build <id>        # build one episode (or: build --all)
python -m history_briefed build <id> --silent --placeholder   # quick dry run, no voice or images
python -m history_briefed smoke             # offline dry run of the first episode
python -m history_briefed compare-voices    # render a test line in several voices
python -m history_briefed queue             # rewrite build/queue.json
python -m history_briefed publish           # copy renders into videos/
```
Outputs land in `build/<id>/`: `video.mp4`, `thumbnail.png`, `captions.srt`, `meta.json`. `queue.json` lists the title, description, tags, UTC time and video URL for each built episode, which is what gets scheduled in Buffer.

## Images (free by default)
`visuals.provider` in `config.yaml` picks where images come from:

| Provider | Cost | Setup |
|---|---|---|
| `pollinations` (default) | Free | None. No account or key. |
| `cloudflare` | Free tier | Free Cloudflare account. Add `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` as environment variables (or repo secrets). |
| `gemini` | Paid | `GEMINI_API_KEY`. The free tier has no image quota, so builds fail with `429 RESOURCE_EXHAUSTED`. |
| `placeholder` | Free | Dark placeholder frames, for testing only. |

Free services are rate-limited, so the builder waits and retries. Generated images are cached in `cache/images/`, so re-running a build doesn't repeat them locally. Free images are generated at 720x1280 and scaled up, so they look slightly softer than paid ones.

## Voice
Narration uses Kokoro (offline, free). The default voice is `bm_george`. Run `compare-voices`, listen to `build/voice_samples/` next to your own voiceover, then set `tts.voice` in `config.yaml`.

## Captions
Your sample video has no burned-in captions, so they are off. An `.srt` file is always written for YouTube. Set `captions.burn_in: true` to try on-screen captions (they are hidden during the outro image).

## Adding or editing an episode
Copy any file in `episodes/`, then change `order`, `id`, the narration and the image prompts. `list` shows the slot it will get. Use `{"kind": "card", "text": "1815", "sub": "optional line"}` for date or number cards. Write years as words in narration ("nineteen thirty-two") so the voice reads them correctly.

## Scheduling in Buffer
Buffer needs a public link for each video. After the workflow runs, each video is at
`https://raw.githubusercontent.com/XyloMining/History-Briefed/main/videos/<id>/video.mp4`
and `videos/queue.json` has the matching title, description, tags and time. Buffer's current plan allows 10 scheduled posts at a time.

## Troubleshooting
- **`429 RESOURCE_EXHAUSTED`:** You're on the `gemini` provider without paid quota. Set `provider: pollinations`.
- **`doctor` says the outro image is missing:** Check both PNGs are in `assets/` with the exact names above.
- **Files starting with a dot (`.gitignore`, `.env.example`, `.github/`) are missing after a zip upload:** Many tools hide dotfiles. Create them directly on github.com.
- **Video is under 20 seconds:** The build stops with an error. Lengthen the narration.
- **Facts:** Check names, dates and figures in each script against sources before filming.
