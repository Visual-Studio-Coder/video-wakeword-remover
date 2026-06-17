# Wake-word Deactivator

A small CLI tool that processes audio/video files and suppresses common wake words like `Siri`, `Alexa`, and `OK Google` by altering the wakeword section and stitching the media back together.

## Install

### Homebrew

This repo includes a Homebrew formula in `Formula/`.

```bash
brew tap Visual-Studio-Coder/video-wakeword-remover https://github.com/Visual-Studio-Coder/video-wakeword-remover
brew install --HEAD wakeword-remover
```

### Python

```bash
python -m pip install .
```

## Usage

```bash
wakeword-remover /path/to/input-media --wakewords "hey siri" siri "ok google"
```

You can also use the explicit subcommand form:

```bash
wakeword-remover process /path/to/input-media --wakewords "hey siri" siri "ok google"
```

## Output

- The tool writes a cleaned duplicate of the input media.
- The output is inferred from the input format when possible.
- The wakeword region is split into `before`, `during`, and `after` segments.
- The `during` segment is processed, then the file is stitched back together.
- The same cleaned file is updated for every wakeword occurrence.

## Python API

```python
from wakeword_remover.cli import process_media

output_path = process_media("input.mp4", wakewords=["hey siri", "ok google"])
print(output_path)
```

## Notes

- Requires `ffmpeg` on your system.
- Punctuation is stripped during wakeword matching.
- Multi-word phrases are supported, for example `"ok google"`.
