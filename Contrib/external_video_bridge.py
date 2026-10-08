#!/usr/bin/env python3
"""Feed openMSX's external_video_file setting from FFmpeg or a test pattern.

FFmpeg emits raw RGB24 frames at 640x480. Each complete frame is published as
an atomic P6 PPM replacement so openMSX never sees a partially written image.
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

WIDTH = 640
HEIGHT = 480
FRAME_BYTES = WIDTH * HEIGHT * 3
HEADER = b"P6\n640 480\n255\n"


def publish(path: Path, rgb: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as output:
        output.write(HEADER)
        output.write(rgb)
    for attempt in range(5):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.01)


def test_pattern(path: Path) -> None:
    rgb = bytearray(FRAME_BYTES)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            i = (y * WIDTH + x) * 3
            rgb[i] = x * 255 // (WIDTH - 1)
            rgb[i + 1] = y * 255 // (HEIGHT - 1)
            rgb[i + 2] = 255 if (x // 40 + y // 40) % 2 else 0
    publish(path, rgb)


def read_frame(stream) -> bytes | None:
    frame = bytearray(FRAME_BYTES)
    view = memoryview(frame)
    offset = 0
    while offset < FRAME_BYTES:
        chunk = stream.readinto(view[offset:])
        if not chunk:
            return None
        offset += chunk
    return frame


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="PPM path used by openMSX's external_video_file setting")
    parser.add_argument("--ffmpeg", default="ffmpeg",
                        help="FFmpeg executable (default: ffmpeg from PATH)")
    parser.add_argument("--test-pattern", action="store_true",
                        help="write one test frame and exit")
    parser.add_argument("ffmpeg_input", nargs=argparse.REMAINDER,
                        help="FFmpeg input arguments after --")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.test_pattern:
        test_pattern(args.output)
        return 0

    input_args = args.ffmpeg_input
    if input_args and input_args[0] == "--":
        input_args = input_args[1:]
    if not input_args:
        parser.error("supply FFmpeg input arguments after --, or use --test-pattern")

    command = [args.ffmpeg, "-hide_banner", "-loglevel", "warning", *input_args,
               "-an", "-vf", f"scale={WIDTH}:{HEIGHT}",
               "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    assert process.stdout is not None
    try:
        while (frame := read_frame(process.stdout)) is not None:
            publish(args.output, frame)
    except KeyboardInterrupt:
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
        process.stdout.close()
        process.wait()
    return process.returncode


if __name__ == "__main__":
    sys.exit(main())
