#!/usr/bin/env python3
"""Feed openMSX's external_video_file setting from FFmpeg or a test pattern.

FFmpeg emits raw RGB24 frames at 640x480. Each complete frame is published as
an atomic P6 PPM replacement so openMSX never sees a partially written image.
"""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time

WIDTH = 640
HEIGHT = 480
FRAME_BYTES = WIDTH * HEIGHT * 3
HEADER = b"P6\n640 480\n255\n"


def capture_backend() -> str:
    if sys.platform == "win32":
        return "dshow"
    if sys.platform == "darwin":
        return "avfoundation"
    if sys.platform.startswith("linux"):
        return "v4l2"
    raise ValueError(f"automatic device selection is unavailable on {sys.platform}")


def device_arguments(device: str) -> list[str]:
    backend = capture_backend()
    if backend == "dshow":
        return ["-f", backend, "-i", f"video={device}"]
    if backend == "avfoundation":
        return ["-f", backend, "-i", f"{device}:none"]
    return ["-f", backend, "-i", device]


def resolve_ffmpeg(requested: str | None) -> str:
    if requested:
        return requested
    if found := shutil.which("ffmpeg"):
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise FileNotFoundError("FFmpeg is not installed") from None


def list_devices(ffmpeg: str, output: Path | None = None) -> int:
    backend = capture_backend()
    if backend == "v4l2":
        devices = [str(path) for path in sorted(Path("/dev").glob("video[0-9]*"))]
        if output:
            output.write_text("\n".join(devices), encoding="utf-8")
        else:
            print("Video4Linux2 devices:", *devices, sep="\n")
        return 0
    if backend == "dshow":
        command = [ffmpeg, "-hide_banner", "-list_devices", "true",
                   "-f", backend, "-i", "dummy"]
    else:
        command = [ffmpeg, "-hide_banner", "-f", backend,
                   "-list_devices", "true", "-i", ""]
    # FFmpeg normally exits with an error after listing devices.
    if output:
        result = subprocess.run(command, capture_output=True, text=True, errors="replace")
        listing = result.stderr + result.stdout
        if backend == "dshow":
            devices = re.findall(r'"([^"]+)" \(video\)', listing)
        else:
            video_listing = listing.split("AVFoundation audio devices:", 1)[0]
            devices = [name for _, name in re.findall(
                r'\[(\d+)\] ([^\r\n]+)', video_listing)]
        output.write_text("\n".join(devices), encoding="utf-8")
    else:
        subprocess.run(command, check=False)
    return 0


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
    parser.add_argument("--output", type=Path,
                        help="PPM path used by openMSX's external_video_file setting")
    parser.add_argument("--ffmpeg", help="FFmpeg executable (default: PATH or imageio-ffmpeg)")
    parser.add_argument("--test-pattern", action="store_true",
                        help="write one test frame and exit")
    parser.add_argument("--list-devices", action="store_true",
                        help="list local video capture devices and exit")
    parser.add_argument("--list-devices-file", type=Path,
                        help="write video device names to a UTF-8 file and exit")
    parser.add_argument("--stop-file", type=Path,
                        help="stop capture when this file is created")
    parser.add_argument("--device", help="capture device name (Windows), index (macOS), or path (Linux)")
    parser.add_argument("ffmpeg_input", nargs=argparse.REMAINDER,
                        help="FFmpeg input arguments after --")
    args = parser.parse_args()
    if args.list_devices or args.list_devices_file:
        return list_devices(resolve_ffmpeg(args.ffmpeg), args.list_devices_file)
    if args.output is None:
        parser.error("--output is required for capture or --test-pattern")
    input_args = args.ffmpeg_input
    if input_args and input_args[0] == "--":
        input_args = input_args[1:]
    if args.device and input_args:
        parser.error("use either --device or FFmpeg input arguments after --")
    if args.device:
        try:
            input_args = device_arguments(args.device)
        except ValueError as error:
            parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.test_pattern:
        test_pattern(args.output)
        return 0

    if not input_args:
        parser.error("supply --device, FFmpeg input arguments after --, or --test-pattern")

    command = [resolve_ffmpeg(args.ffmpeg), "-hide_banner", "-loglevel", "warning", *input_args,
               "-an", "-vf", f"scale={WIDTH}:{HEIGHT}",
               "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE)
    assert process.stdout is not None
    if args.stop_file:
        def watch_stop() -> None:
            while process.poll() is None:
                if args.stop_file.exists():
                    process.terminate()
                    return
                time.sleep(0.1)
        threading.Thread(target=watch_stop, daemon=True).start()
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
    try:
        sys.exit(main())
    except FileNotFoundError:
        print("Video capture failed: FFmpeg executable not found. "
              "Install FFmpeg or pass --ffmpeg PATH.", file=sys.stderr)
        sys.exit(1)
