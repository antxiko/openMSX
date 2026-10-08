# External video preview

This branch can put a live external video frame behind transparent MSX pixels.
It is a frame-based preview of superimpose. Digitization into VRAM, external
audio, external-only mode, analog line/phase synchronization, and the NMS 8280
front-panel controls are still pending.

## Quick test

Run from the repository root:

```powershell
python Contrib/external_video_bridge.py --output external-video.ppm --test-pattern
```

Start the newly built openMSX, then enter this in its console (F10), using the
absolute path to the generated file:

```tcl
set external_video_file C:/path/to/external-video.ppm
```

On an MSX2 machine with the optional video functions, select superimpose with
`SET VIDEO 2 : COLOR ,0,0` in BASIC. For a development preview on another
V9938 machine, R#9 bits 5:4 must equal `01`, R#8 bit 5 must be clear, and
background color index 0 must be used. The NMS 8280 machine definition needs
its own disk ROM (`nms8280_disk.rom`, SHA-1
`69f3dbfc1d516cd09a1a7e286049f99e37ca90d9`) in the normal openMSX ROM
search path. ROM binaries are not included here.

## Live capture

Install FFmpeg and pass its input options after `--`. The bridge scales decoded
frames to 640x480 RGB and publishes only complete frames. In PowerShell, for a
Windows DirectShow device:

```powershell
ffmpeg -list_devices true -f dshow -i dummy
python Contrib/external_video_bridge.py --output external-video.ppm -- -f dshow -i 'video=DEVICE NAME'
```

On Linux, a typical Video4Linux2 input uses
`-- -f v4l2 -i /dev/video0`. On macOS, AVFoundation uses
`-- -f avfoundation -i '0:none'`; select the correct device index first.
If FFmpeg is not in `PATH`, supply `--ffmpeg /path/to/ffmpeg` before `--`.
Device formats and PAL/NTSC settings must be chosen for the actual capture
device. See [FFmpeg input device documentation](https://www.ffmpeg.org/ffmpeg-devices.html).

The tested path used FFmpeg's moving `testsrc2` source and a Philips NMS 8255
with its local ROMs. Two screenshots showed different external frames behind
the MSX BASIC text. No USB capture device or NMS 8280 ROM was used in that
test.
