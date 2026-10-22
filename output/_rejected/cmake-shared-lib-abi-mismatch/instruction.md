The project at `/app` builds without a single error or warning, but when you run `/app/build/geom_app`, the computed values are completely wrong. A colleague built this geometry processing library and is stumped — the build is perfectly clean.

The expected output should show:
- Diffuse lighting coefficient ≈ 0.577350
- Right-triangle area = 0.500000

The project has two shared libraries (`libmath` and `librender`) and a main program. Both libraries share the `Vec3` struct defined in `types.h`.

Your task: figure out what's wrong, fix it, then clean the build directory (`rm -rf /app/build`), rebuild from scratch (`cd /app/build && cmake .. && make`), and verify the program prints the correct values. The fix must ensure the two shared libraries have a consistent view of the `Vec3` type.
