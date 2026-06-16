# Wake-word Deactivator

https://x.com/bryanwangxin/status/2064309590414836085

> In Apple's keynote video, whenever Siri is mentioned, the audio is cut at the 3k, 4k, 5k, and 6kHz frequency bands to prevent nearby Apple devices from activating Siri while viewers watch the video.

When Apple says “Siri” in a keynote, they deliberately suppress specific frequencies in the audio so it doesn’t trigger nearby devices. This project does the same thing for your content.

It’s a small CLI tool that processes audio and video files so wake words like “Hey Siri”, “Alexa”, “OK Google”, etc. are less likely to trigger nearby smart assistants.

## Requirements

- Python environment managed by `uv`
- `ffmpeg` available on your system
- `mlx_whisper` and `ffmpeg-python` installed through the project dependencies

## Usage

The tool accepts any audio or video file that `ffmpeg` can decode.

```bash
uv run main.py process /path/to/input-media --wakewords "hey siri" siri "ok google" --output /path/to/output
```

You can also omit `process` and pass the input path directly:

```bash
uv run main.py /path/to/input-media --wakewords "hey siri" siri "ok google" --output /path/to/output
```

### Output behavior

- If `--output` is omitted, the tool writes a sibling file named like:
  - `input_cleaned.mp3`
  - `input_cleaned.m4a`
  - `input_cleaned.mp4`
- The output container is inferred from the input media with `ffmpeg`/`ffprobe`.
- If the input filename extension is misleading, the tool uses the detected media container family so the output is still valid.
- The wakeword region is split into before / during / after, the `during` portion is processed, then the pieces are stitched back together.
- The same cleaned file is updated for every wakeword occurrence, so the final result contains all processing passes.

### Wakeword matching

- Matching is phrase-based.
- Punctuation is stripped before comparison.
- Use quotes around multi-word phrases.

### Example

```bash
uv run main.py process keynote.mov --wakewords "hey siri" "ok google"
```

That will produce a cleaned duplicate in the same media format family as the source file.

### Example files

Listen to the before/after pair:

- [New Recording 10.wav](wakeword-remover/New%20Recording%2010.wav)
- [New Recording 10_cleaned.wav](wakeword-remover/New%20Recording%2010_cleaned.wav)

The second file shows the processed output after wakeword suppression is applied.
