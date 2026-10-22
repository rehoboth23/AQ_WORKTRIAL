# audiomix - Audio Processing Library

A C++ audio processing library providing real-time DSP operations on WAV audio
files. The project consists of two shared libraries and a command-line tool.

## Architecture

- **libaudiomix.so** - Core processing engine with audio processors
- **libaudioformat.so** - WAV I/O and pipeline orchestration
- **audiomix-cli** - Command-line interface

## Features

- **Double-precision processing** - Configurable at runtime for maximum fidelity.
  The library automatically selects the optimal precision based on the input
  format and available hardware. No special configuration needed.
- **Multiple processors**: normalize, gain, limiter, compressor
- **Stereo WAV support**: 16-bit PCM at any sample rate
- **Analysis mode**: RMS, peak, and clipping detection per channel

## Building

```bash
mkdir build && cd build
cmake .. && make -j$(nproc)
```

## Usage

### Process audio
```bash
audiomix-cli process input.wav output.wav normalize 0
audiomix-cli process input.wav output.wav gain 6
audiomix-cli process input.wav output.wav limiter -3
audiomix-cli process input.wav output.wav compressor 4
```

### Analyze audio
```bash
audiomix-cli analyze input.wav
```

Output format: `rms_left=X rms_right=X peak_left=X peak_right=X clipping=X clip_count=X`

## Processor Reference

| Processor | Param | Description |
|-----------|-------|-------------|
| normalize | target_dB | Normalize to target peak level (0 = 0 dBFS) |
| gain | dB | Apply gain in decibels |
| limiter | threshold_dB | Hard limit at threshold |
| compressor | ratio | Dynamic range compression |

## Notes

The analysis module is loaded dynamically at runtime for plugin compatibility.
If the analysis module is not available, the analyze command will report an error.
This is expected behavior when the module is not installed.
