import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import ffmpeg
import mlx_whisper

DEFAULT_WAKEWORDS = [
    "hey computer",
    "ok computer",
    "hello computer",
    "siri",
    "alexa",
    "google",
    "ok google",
]

MULTIMEDIA_FAMILY_SUFFIXES = {".mov", ".mp4", ".m4a", ".3gp", ".3g2", ".mj2"}
AUDIO_SUFFIXES = {
    ".aac",
    ".flac",
    ".m4a",
    ".mp3",
    ".oga",
    ".ogg",
    ".opus",
    ".wav",
}
VIDEO_SUFFIXES = {
    ".avi",
    ".mkv",
    ".mov",
    ".mp4",
    ".m4v",
    ".webm",
    ".3gp",
    ".3g2",
    ".mj2",
}


def _safe_label(text: str) -> str:
    return (
        re.sub(r"[^a-zA-Z0-9._-]+", "_", text.strip().lower()).strip("_") or "wakeword"
    )


def _normalize_token(text: str) -> str:
    normalized = re.sub(r"[\W_]+", "", text.strip().lower())
    if normalized == "okay":
        return "ok"
    return normalized


def _trim_video(stream, start=None, end=None):
    kwargs = {}
    if start is not None:
        kwargs["start"] = start
    if end is not None:
        kwargs["end"] = end
    return stream.filter("trim", **kwargs).filter("setpts", "PTS-STARTPTS")


def _trim_audio(stream, start=None, end=None):
    kwargs = {}
    if start is not None:
        kwargs["start"] = start
    if end is not None:
        kwargs["end"] = end
    return stream.filter("atrim", **kwargs).filter("asetpts", "PTS-STARTPTS")


def _soften_audio(stream):
    softened = stream
    for frequency in (3000, 4000, 5000, 6000):
        softened = softened.filter(
            "equalizer", f=frequency, width_type="q", width=1.0, g=-10
        )
    return softened


def _merge_intervals(intervals):
    if not intervals:
        return []

    merged = [intervals[0].copy()]
    merged[0]["labels"] = [merged[0]["label"]]

    for interval in intervals[1:]:
        last = merged[-1]
        if interval["start"] <= last["end"]:
            last["end"] = max(last["end"], interval["end"])
            last["labels"].append(interval["label"])
        else:
            next_interval = interval.copy()
            next_interval["labels"] = [next_interval["label"]]
            merged.append(next_interval)

    return merged


def _find_wakeword_intervals(words, wakewords):
    normalized_words = [_normalize_token(word.get("word", "")) for word in words]
    intervals = []

    for wakeword in wakewords:
        phrase_tokens = [_normalize_token(token) for token in wakeword.split()]
        if not phrase_tokens or any(not token for token in phrase_tokens):
            continue

        span_length = len(phrase_tokens)
        for index in range(0, len(words) - span_length + 1):
            if normalized_words[index : index + span_length] == phrase_tokens:
                intervals.append(
                    {
                        "label": wakeword,
                        "start": words[index]["start"],
                        "end": words[index + span_length - 1]["end"],
                    }
                )

    intervals.sort(key=lambda interval: (interval["start"], interval["end"]))
    return _merge_intervals(intervals)


def _is_multimedia_family(format_name: str) -> bool:
    return any(token in MULTIMEDIA_FAMILY_SUFFIXES for token in format_name.split(","))


def _infer_output_suffix(source_path: Path, probe: Any, has_video: bool) -> str:
    source_suffix = source_path.suffix.lower()
    format_name = probe.get("format", {}).get("format_name", "")

    if source_suffix in (AUDIO_SUFFIXES | VIDEO_SUFFIXES):
        if source_suffix in VIDEO_SUFFIXES:
            return source_suffix

        if has_video:
            return ".mp4"

        if source_suffix == ".wav" and _is_multimedia_family(format_name):
            return ".m4a"

        return source_suffix

    if "wav" in format_name:
        return ".wav"
    if "flac" in format_name:
        return ".flac"
    if "mp3" in format_name:
        return ".mp3"
    if "aac" in format_name:
        return ".aac"
    if "ogg" in format_name:
        return ".ogg"
    if "opus" in format_name:
        return ".opus"
    if "webm" in format_name:
        return ".webm"
    if "matroska" in format_name or "mkv" in format_name:
        return ".mkv"
    if _is_multimedia_family(format_name):
        return ".mp4" if has_video else ".m4a"

    return ".mp4" if has_video else ".m4a"


def _output_encoding_kwargs(output_suffix: str, has_video: bool):
    if output_suffix == ".wav":
        return {"acodec": "pcm_s16le"}
    if output_suffix == ".flac":
        return {"acodec": "flac"}
    if output_suffix == ".mp3":
        return {"acodec": "libmp3lame"}
    if output_suffix in {".m4a", ".mp4", ".m4v", ".mov", ".aac"}:
        kwargs = {"acodec": "aac"}
        if has_video:
            kwargs["vcodec"] = "libx264"
        return kwargs
    if output_suffix in {".webm"}:
        kwargs = {"acodec": "libopus"}
        if has_video:
            kwargs["vcodec"] = "libvpx-vp9"
        return kwargs
    if output_suffix in {".ogg", ".oga", ".opus"}:
        return {"acodec": "libopus"}
    if output_suffix == ".avi":
        kwargs = {"acodec": "mp3"}
        if has_video:
            kwargs["vcodec"] = "mpeg4"
        return kwargs
    if output_suffix == ".mkv":
        kwargs = {"acodec": "aac"}
        if has_video:
            kwargs["vcodec"] = "libx264"
        return kwargs

    kwargs = {"acodec": "aac"}
    if has_video:
        kwargs["vcodec"] = "libx264"
    return kwargs


def _resolve_output_path(
    input_path: Path, probe: Any, has_video: bool, output_arg: str | Path | None
):
    inferred_suffix = _infer_output_suffix(input_path, probe, has_video)

    if output_arg is None:
        return input_path.with_name(f"{input_path.stem}_cleaned{inferred_suffix}")

    requested = Path(output_arg)
    if requested.exists() and requested.is_dir():
        return requested / f"{input_path.stem}_cleaned{inferred_suffix}"

    if requested.suffix:
        return requested

    return requested.with_suffix(inferred_suffix)


def _process_interval(source_path, destination_path, start, end, has_video, has_audio):
    media_input = ffmpeg.input(str(source_path))

    if has_video and has_audio:
        before_video = _trim_video(media_input.video, end=start)
        during_video = _trim_video(media_input.video, start=start, end=end)
        after_video = _trim_video(media_input.video, start=end)

        before_audio = _trim_audio(media_input.audio, end=start)
        during_audio = _soften_audio(
            _trim_audio(media_input.audio, start=start, end=end)
        )
        after_audio = _trim_audio(media_input.audio, start=end)

        ffmpeg.concat(
            before_video,
            before_audio,
            during_video,
            during_audio,
            after_video,
            after_audio,
            v=1,
            a=1,
        ).output(
            str(destination_path),
            **_output_encoding_kwargs(destination_path.suffix.lower(), True),
        ).run(overwrite_output=True)
        return

    if has_video:
        before_video = _trim_video(media_input.video, end=start)
        during_video = _trim_video(media_input.video, start=start, end=end)
        after_video = _trim_video(media_input.video, start=end)
        ffmpeg.concat(before_video, during_video, after_video, v=1, a=0).output(
            str(destination_path),
            **_output_encoding_kwargs(destination_path.suffix.lower(), True),
        ).run(overwrite_output=True)
        return

    if has_audio:
        before_audio = _trim_audio(media_input.audio, end=start)
        during_audio = _soften_audio(
            _trim_audio(media_input.audio, start=start, end=end)
        )
        after_audio = _trim_audio(media_input.audio, start=end)
        ffmpeg.concat(before_audio, during_audio, after_audio, v=0, a=1).output(
            str(destination_path),
            **_output_encoding_kwargs(destination_path.suffix.lower(), False),
        ).run(overwrite_output=True)
        return

    raise RuntimeError("Input media has no audio or video streams.")


def process_media(
    input_path: str | Path,
    wakewords: list[str] | None = None,
    output: str | Path | None = None,
):
    source_path = Path(input_path)
    selected_wakewords = DEFAULT_WAKEWORDS if wakewords is None else wakewords

    transcript: Any = mlx_whisper.transcribe(str(source_path), word_timestamps=True)
    words = [
        word
        for segment in transcript.get("segments", [])
        for word in segment.get("words", [])
    ]

    probe: Any = ffmpeg.probe(str(source_path))
    has_video = any(
        stream.get("codec_type") == "video" for stream in probe.get("streams", [])
    )
    has_audio = any(
        stream.get("codec_type") == "audio" for stream in probe.get("streams", [])
    )

    if not has_audio and not has_video:
        raise RuntimeError("Input media has no audio or video streams.")

    output_file = _resolve_output_path(source_path, probe, has_video, output)
    temp_file = output_file.with_name(f"{output_file.stem}.tmp{output_file.suffix}")

    matches = _find_wakeword_intervals(words, selected_wakewords)

    shutil.copy2(source_path, output_file)

    if not matches:
        print(f"No wakewords found; copied input to {output_file}")
        return output_file

    current_path = output_file
    for match in reversed(matches):
        labels = ", ".join(match["labels"])
        print(
            f"Processing wakeword(s): {labels} at {match['start']}s - {match['end']}s"
        )
        _process_interval(
            current_path,
            temp_file,
            match["start"],
            match["end"],
            has_video,
            has_audio,
        )
        temp_file.replace(output_file)
        current_path = output_file

    print(f"Wrote cleaned output to {output_file}")
    return output_file


def _build_parser():
    parser = argparse.ArgumentParser(
        description="Deactivate wake words in media files."
    )
    parser.add_argument(
        "input",
        help="Path to an input audio or video file that ffmpeg can decode.",
    )
    parser.add_argument(
        "--wakewords",
        nargs="*",
        default=DEFAULT_WAKEWORDS,
        help='Wake words or phrases to process. Example: --wakewords "hey siri" siri "ok google"',
    )
    parser.add_argument(
        "--output",
        help="Optional output file or directory. Defaults to a sibling *_cleaned file using the input media format.",
    )
    return parser


def _main(argv: list[str] | None = None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    print("Hello from wakeword-remover!")
    process_media(args.input, args.wakewords, args.output)


def main():
    argv = sys.argv[1:]
    if argv and argv[0] == "process":
        argv = argv[1:]
    _main(argv)


if __name__ == "__main__":
    main()
