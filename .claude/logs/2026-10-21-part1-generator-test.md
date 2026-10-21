# Part 1 generator — test record (2026-10-21)

Goal: `generate.sh "<topic>"` produces a task that passes the structural validator, oracle (reward 1) and nop (reward 0).

## 1. Offline checks (no model calls, no Docker)
| Check | Result |
|---|---|
| `parse_spec` on a fenced JSON reply | name slugified to `fix-the-widget` ✅ |
| `clean_files` drops forbidden paths | `tests/test.sh` and `../escape.txt` dropped; 4 model files kept ✅ |
| Canary placement | after the `#!` in solve.sh and the `# syntax=` line in the Dockerfile ✅ |
| `task.toml` + `validate.sh` on the fake task | `PASSED: All structural checks passed.` ✅ |
| `generate.py --help` / `--bogus` | usage shown, exit 0 / "unrecognized arguments", exit 2 ✅ |
| `_pytest_excerpt` on the real SQLite round-0 output | starts at `test session starts`, keeps the FAILED line, no apt noise, 2,837 vs 5,018 chars; falls back to the tail when pytest never ran ✅ |

## 2. Checks module on a known-good fake task (Docker, no model)
`run_all()` → validator ✅, oracle reward 1.0 (22 s) ✅, nop reward 0.0 (16 s) ✅

## 3. Real generations (glm-5.1 via `scripts/generate.sh`)
| Topic → task | Rounds | Round 0 failure → repair | Tokens (in / out) | Time |
|---|---|---|---|---|
| C Makefile/linker → `fix-c-makefile-lib-reorg` | 1 | none needed | 3,422 / 55,356 | 696 s |
| SQLite migration → `fix-sqlite-migration-corruption` | 2 | oracle 0: test crashed on `json.loads("")` (sqlite3 `-json` prints nothing for 0 rows). Repair added an empty-output guard in the helper; the assertion is unchanged. | 8,066 / 17,506 | 280 s |
| nginx proxy → `nginx-proxy-swapped-routes` | 2 | oracle 0: solve.sh bug. Repair changed only solve.sh. | 8,048 / 48,280 | 628 s |
| Pillow upgrade → `pillow-10-resampling-migration` (run with the new argparse CLI) | 2 | oracle 0: tests called `python3`, which in the verifier is uv's Python with no Pillow. Repair switched to `/usr/local/bin/python3`; still 8 tests, no assertion changed. | 10,713 / 61,078 | 692 s |

**Yield: 4/4 topics → valid, correct tasks.** 3 of 4 needed exactly one repair round.
Totals: 30,249 input / 182,220 output tokens, about 38 min of wall time (3 ran in parallel). The gateway doesn't return a dollar cost, so cost is reported as tokens.

## 4. Independent re-check (plain Harbor CLI, not the generator's code)
For each of the first 3 tasks: `validate.sh` → PASSED; `harbor run -a oracle` → reward 1.0, no exception; `harbor run -a nop` → reward 0.0, no exception.
Canary (`grep -c` for the dataset GUID): 1 each in the Dockerfile, solve.sh and test_outputs.py, and 0 in instruction.md. This holds for all 4 tasks.

## 5. Manual review (answer leaks, weakened tests)
- No solution or expected output is copied into any image. Build-time helpers are deleted (`setup_db.sh`, the libgraph sources).
- All three repairs fixed a real defect and none removed or loosened an assertion.
- SQLite: fair. The corruption is a column shift, so the original values can be recovered from the database itself.
- nginx: the instruction says the processes are "managed by supervisord", but Harbor overrides `CMD` with `sleep infinity`, so nothing runs at the start. The task is still solvable (the agent can start the services). This is a prompt fix, carried to Part 2.

## Not covered
- The difficulty band (the 5-run terminus-2 eval) is Part 2.
- A run that ends in `status: failed` after 3 repairs hasn't happened yet. That path (moving the task to `last-attempt/` and writing `summary.json`) has only been checked by reading the code.
