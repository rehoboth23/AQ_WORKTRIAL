The csvtools project at /app is a C++ CSV processing tool with a plugin architecture. It compiles without errors, but at runtime filter plugins fail to load with "undefined symbol" errors from the dynamic linker.

Fix the project so that running `./csvtools ../data/sample.csv` from /app/build processes the CSV through the trim and uppercase filter plugins and prints the result to stdout.

Requirements:
- The program must exit with code 0 and produce no "Failed to load plugin" messages on stderr.
- The shared library /app/build/libcsvtools.so must export its public API symbols (visible via `nm -D`), including `register_filter` and the typeinfo for `csvtools::Filter`.
- Internal implementation symbols from the `csvtools::detail` namespace must remain hidden — they must NOT appear in the dynamic symbol table.
- The expected output after processing sample.csv through both filters is:
```
NAME,AGE,CITY
ALICE,30,NYC
BOB,25,LA
CHARLIE,35,CHICAGO
```

The project source is in /app and has been pre-built in /app/build. Fix the source and rebuild.
