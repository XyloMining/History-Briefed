# History Briefed

Builds each History Briefed Short from a single episode file: narration, visuals, the fixed outro, thumbnail, title, tags, description and a posting slot (Mon/Wed/Fri 4:00 PM Sydney time).

## One-time setup
```bash
pip install -r requirements.txt
python -m history_briefed setup      # downloads the Kokoro voice model
cp .env.example .env                 # add GEMINI_API_KEY for AI images (optional for dry runs)
```
Add these files to `assets/` (they are large images, so they are not committed by the tool):
- `unique_outro_vertical.png` and `unique_outro_horizontal.png` (the iconic outro image)
- `voiceover_reference.wav` (your sample voiceover, used only to compare voices)

Then run `python -m history_briefed doctor`.

## Everyday use
```bash
python -m history_briefed list                  # episodes and their slots
python -m history_briefed build 01              # build one (or: build --all)
python -m history_briefed smoke                 # offline dry run, placeholders + silent track
python -m history_briefed compare-voices        # render a line in several voices to match yours
python -m history_briefed publish               # copy renders to videos/ for public URLs
```
Outputs land in `build/<id>/`: `video.mp4`, `thumbnail.png`, `captions.srt`, `meta.json`; `build/queue.json` lists title, description, tags, UTC time and video URL for each episode, which is what gets scheduled in Buffer.

## How a video is assembled
`hook -> body scenes -> "Subscribe for more stories like this, and comment what I should brief next." -> iconic image over "History doesn't disappear... it just gets briefed."`

Each scene is voiced separately so image timing follows the real narration. Every Short must be at least 20 seconds (`video.min_seconds`).

## Adding an episode
Copy any file in `episodes/`, change `order`, `id`, text and image prompts. `list` shows the slot it will get. Use `{"kind": "card", "text": "1815"}` for date/number cards.

## Things to confirm
- `tts.voice` (default `bm_george`): run `compare-voices` and match it to your voiceover.
- Captions are off by default because the sample video has none burned in. Set `captions.burn_in: true` to try them.
- AI images need `GEMINI_API_KEY`; without it you get dark placeholder frames.
- Episode facts should be checked against sources before filming.
