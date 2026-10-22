The audiomix project at `/app` builds cleanly with CMake (already built in `/app/build`) but its CLI tool does not work correctly. Fix it so that BOTH commands produce correct results:

1. `audiomix-cli process <input.wav> <output.wav> <processor> <param>` — applies an audio processor (e.g., `normalize 0`) and writes the result as a valid WAV. The output must have the same sample rate and channel count as the input, and normalization must bring the peak amplitude to 0 dBFS (within ±0.5 dB).
2. `audiomix-cli analyze <input.wav>` — prints RMS levels, peak levels, and clipping status to stdout in the format: `rms_left=X rms_right=X peak_left=X peak_right=X clipping=X clip_count=X` where X values are in dB (or `inf` for silence).

Test WAV files are in `/app/test_data/`. The tool must handle normal audio and edge cases like silence correctly. After fixing, rebuild with `cd /app/build && cmake .. && make -j$(nproc)`.
