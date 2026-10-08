# External video and genlock work

Target order: Philips NMS 8280, then Sony HB-F900 with HBI-F900 AV Creator.
The Sony HBI-V1 cartridge is a separate, later target.

## Current openMSX integration points

- `VDP::setExternalVideoSource()` accepts a `RawFrame`; Pioneer LaserDisc
  already feeds it through `PioneerLDControl::updateVideoSource()`.
- `VDP` enables that source for superimpose when bit 0 of VDP register 0 is
  set. `PixelRenderer` and `SDLRasterizer` pass the frame to the rasterizer.
- `Video9000` is another example of video composition, but combines two
  emulated outputs rather than a host capture device.
- There is a Sony HB-F900 machine definition, including its video utility ROM.
  This branch adds an initial NMS 8280 definition. The HB-F900 definition
  explicitly says its digitize and superimpose functions are not emulated.
- No NMS 8280 digitizer input is implemented in `VDPCmdEngine`.

## Hardware behavior to establish before emulation

The NMS 8280 `SET VIDEO` firmware exposes normal, digitize, superimpose,
and external-only modes. The published example uses `SCREEN 8`, `SET VIDEO 1`,
and `COPY SCREEN` to digitize. Ports F6/F7 and VDP external-video bits need
register-level confirmation from the service manual, firmware, or real-hardware
traces. The front-panel source selector and level sliders also need a host-side
representation. In particular, a displayed captured frame does not prove that
`COPY SCREEN` writes the correct bytes to VRAM.

## Current preview path

The `external_video_file` setting accepts a 640x480 P6 PPM file. The VDP
reloads one complete image at each frame boundary and uses the last valid
image if a writer is in the middle of replacing it. The path is available on
all machines for development. On a V9938, external superimpose is selected by
R#9 bits 5:4 = 01 with transparent background pixels (R#8 bit 5 clear).
This is a frame-based preview; it does not emulate analog
genlock phase, digitization into VRAM, or the NMS 8280 front-panel controls.

Generate a still frame with:

```
python Contrib/external_video_bridge.py --output external-video.ppm --test-pattern
```

From the openMSX console, set `external_video_file` to its absolute path and
select superimpose in MSX2 BASIC with `SET VIDEO 2 : COLOR ,0,0`. A machine
without the NMS 8280 video hardware can be used to inspect the VDP path but
does not thereby become an NMS 8280. To feed live video once FFmpeg can open
the selected capture device, run the bridge with FFmpeg input arguments after
`--`, for example `-- -f dshow -i video=DEVICE_NAME` on Windows. FFmpeg must be
installed separately. The bridge publishes each complete frame atomically.
FFmpeg's official device documentation lists DirectShow (`dshow`) on Windows,
Video4Linux2 (`v4l2`) on Linux, and AVFoundation (`avfoundation`) on macOS:
https://www.ffmpeg.org/ffmpeg-devices.html

The preview was checked with a 640x480 test pattern and with FFmpeg's moving
`testsrc2` source on a Philips NMS 8255 using the new executable. Screenshots
showed the external frame behind MSX BASIC text and a changed external frame
two seconds later. This verifies frame-based visual composition, not USB
capture, NMS 8280 hardware behavior, digitization, or analog synchronization.

The Sony HB-F900 Video I/F and HBI-F900 AV Creator must be modeled separately.
Do not infer HBI-F900 behavior from HBI-V1 documentation.

## Proposed implementation order

1. Verify the NMS 8280 machine definition against its ROMs, I/O, and clock
   mappings. Keep ROM binaries outside the repository.
2. Extend the external frame source beyond deterministic test
   frames. Define color format, dimensions, timestamp and field order at the
   boundary so the eventual USB backend does not determine emulated behavior.
3. Emulate the NMS 8280 video control and its composition modes. Test the
   visible output with deterministic frames.
4. Emulate the NMS 8280 digitizer path into VDP VRAM, including `COPY SCREEN`,
   and compare captured VRAM against expected SCREEN 8 data.
5. Add a cross-platform live capture backend and device selection after its
   device and supported formats are known. Document latency and whether its
   output is frame-based or synchronized at line/phase level.
6. Model the HB-F900/HBI-F900 combination using its own firmware and hardware
   evidence.

## Sources

- NMS 8280 service manual:
  https://download.file-hunter.com/Manuals/Philips%20NMS%208280%20Service%20Manual.pdf
- NMS 8280 disk ROM dump identification:
  https://www.msx.org/pt-br/node/59225
- MAME MSX2 machine slot map (older NMS 8280 disk dump marked bad):
  https://github.com/mamedev/mame/blob/master/src/mame/msx/msx2.cpp
- blueMSX description of NMS 8280 modes and digitization:
  https://www.msxblue.com/manual/digitization_c.htm
- blueMSX NMS 8280 digitizer implementation, useful as a comparison rather
  than hardware proof:
  https://github.com/libretro/blueMSX-libretro/blob/master/Src/Memory/romMapperNms8280VideoDa.c
- HB-F900 and HBI-F900 overview:
  https://www.msxblue.com/manual/hbf900_c.htm
