# Changelog

Document what you did, why, and any design tradeoffs here.

## 2026-10-21: Pinned Python environment with uv

**What:** Python 3.12 (installed by uv) in a gitignored `.venv` at the repo root, with the generator deps and `harbor` installed. `scripts/generate.sh` and `scripts/validate.sh` now use `.venv/bin/python` when it exists and fall back to `python` otherwise.

**Why:** The host had only macOS `python3` 3.9.6 (too old for `tomllib` and 3.12+ code) and no bare `python`, so both scripts failed. Without `harbor` installed, the validator also silently skipped Harbor's own schema check.

**Tradeoffs:**
- *uv venv vs. a Docker "tools" container.* A container would isolate more, but `harbor run` starts its own containers. The tools container would then need the host Docker socket (root-level access to Docker) and the repo mounted at the same absolute path so Harbor's bind mounts resolve. uv is lighter and avoids that setup, and Docker stays dedicated to task containers.
- *Venv inside the repo vs. outside.* Inside is uv's convention and keeps the project self-contained. `.gitignore` already excludes `.venv/`, so the ~240 MB never gets committed.

## 2026-10-21: validate.sh path fix and environment review

**validate.sh relative paths.** `bash scripts/validate.sh examples/fix-git` failed when run from the repo root ("Directory does not exist"). The script only rewrote the path when it *didn't* exist relative to the caller, then `cd`'d into `validator/`, which broke the relative path. It now makes the path absolute before the `cd`. It checks the caller's folder first, then the repo root, and passes missing paths through so the validator reports them. Tested from the repo root, `examples/`, `/tmp`, with an absolute path, with `.`, and with a missing folder (exit 1). `generate.sh` takes a topic, not a path, and the generator builds `output/` from its own file location, so it never had this bug.

**Validator rules kept as-is.** `validator/validate.py` is unchanged from the starter repo. Its rules (agent `timeout_sec` ≥ 3600, `[task].name` in `org/name` form, `[metadata].difficulty` set) come from there, and the 3600 matches all six examples. The one-hour floor is how the starter repo enforces the README's "timeouts don't count as the model failing", so relaxing it would let tasks fail on time alone.

**Scaffold vs. validator.** Harbor's scaffold (`harbor/src/harbor/cli/template-task/`) fails the validator as-is: agent timeout 900, no name, no difficulty, and its pytest files sit in `pytest-tests/` instead of `tests/`. Decision: treat the scaffold only as a starting point. The generator overwrites the values that break the validator, and `harbor/` stays unedited so it keeps matching the installed Harbor version.

**Environment findings, recorded in CLAUDE.md:**
- Claude's shell doesn't load `~/.zprofile`, so `docker` isn't on its PATH, and Harbor calls `docker compose` as a subprocess. Harbor commands therefore need `PATH="$HOME/.docker/bin:$PATH"`. Verified with `harbor run -p examples/fix-git -a oracle` → reward 1.0.
- `OPENROUTER_API_KEY` / `OPENROUTER_API_BASE` must be exported in the terminal that launches the editor/Claude.
- There are no unit tests or linters; the checks are validate.sh plus oracle/nop. `harbor run` output goes to `jobs/`.

## 2026-10-21: API key via .env

**What:** The key lives in a repo-root `.env`, which is gitignored (the starter `.gitignore` already listed it) and `chmod 600`. `generator/config.py` loads it with python-dotenv (now in `generator/requirements.txt`), and `harbor run` gets it through `--env-file .env`. `.env.example` documents the two variables with no values. In CLAUDE.md, "never store secrets in files" became "never read, print, or copy `.env`".

**Why:** Shell exports depend on which profile a shell loads. Claude's shell skips `~/.zprofile`, so the key wasn't reaching it, and an unattended or resumed batch run needs the key no matter how it's launched.

**Tradeoffs:** macOS Keychain avoids keeping the key in plain text on disk, but it only reaches processes whose shell profile runs. That's fragile for this pipeline. `.env` is the convention the starter repo planned for; the file is gitignored and readable only by its owner, and the key is budget-capped and can be rotated. Exported variables override the file (`load_dotenv` defaults to `override=False`).

## 2026-10-21: Inference endpoint set only in .env

**What:** `OPENROUTER_API_BASE` now comes only from `.env`. The hard-coded fallback in `generator/config.py` and the value in `.env.example` were removed. `.gitignore` now ignores `.env*` (keeping `.env.example`), so backups of `.env` can't be committed.

**Why:** The README's gateway returned 401 for the provided key. With the endpoint set in `.env`, both glm-5.1 (generator, openai client) and glm-5.3-flash (evaluator, through LiteLLM as Harbor calls it) responded. Keeping the URL out of code and docs means a wrong default can't silently send the key to the wrong endpoint, and changing the endpoint is a one-line edit to `.env`.

**Tradeoff:** If `.env` is missing the endpoint, model calls fail instead of falling back. That's intended: failing loudly is better than sending the key to an unintended server.

## 2026-10-21: Part 1 generator (spec → files → checks → repair)

**What:** `generate_task()` now builds a full Harbor task from a topic and only keeps it if it is correct.
1. glm-5.1 writes a design spec as JSON (scenario, hidden state, solution outline, test plan, anti-cheat notes, likely failure modes).
2. glm-5.1 writes the task files from the spec: `instruction.md`, `environment/**`, `solution/solve.sh`, `tests/test_outputs.py`.
3. Python writes the rest: `task.toml`, `tests/test.sh` (the scaffold's pytest runner) and the canary.
4. Checks run in order: structural validator → `harbor run -a oracle` (reward must be 1) → `harbor run -a nop` (reward must be 0).
5. If a check fails, its error output (validator messages, solve.sh output, pytest output, build exception) goes back to glm-5.1, which returns fixed files. Up to `MAX_REPAIR_ROUNDS` (3) rounds.

New modules: `generator/llm.py` (client, retries, reply parsers), `generator/prompts.py`, `generator/checks.py`. New config knobs: `LLM_TIMEOUT_SEC`, `LLM_MAX_RETRIES`, `MAX_REPAIR_ROUNDS`, `TASK_ORG`, `GEN_LOGS_DIR`, `JOBS_DIR`.

**Where things go:** a passing task lands in `output/<task-name>/` and is never overwritten (a name clash gets a time suffix). Every run, pass or fail, leaves an audit trail in `output/_logs/<topic-slug>-<timestamp>/`: `spec.json`, each raw model reply, `events.jsonl` (calls, tokens, check results per round) and `summary.json`. A failed task's last attempt is moved to `last-attempt/` inside its log folder, so `output/` only holds tasks that passed.

**Why / tradeoffs:**
- *Two stages vs. one call.* Designing first (no code) makes the model commit to the hidden state, the fix and the tests before writing anything, and gives later stages (difficulty tuning) a spec to edit. Costs one extra call.
- *File blocks vs. JSON for code.* Code inside JSON breaks on escaping; `<<<FILE path>>> … <<<END>>>` blocks don't need any.
- *Python owns task.toml, test.sh and the canary.* These are fixed boilerplate where model mistakes would only cause validator failures. The model may only write the four content paths and `environment/**`; other paths (e.g. `tests/test.sh`, `../x`) are dropped.
- *Repair loop vs. fail fast.* Most first drafts fail on small things (a missing package, a wrong path). Feeding the real error back is cheap compared with a fresh generation. The repair prompt forbids weakening tests to make them pass.
- *Oracle timeout capped at 1/4 of the agent timeout* (15 min) so a hanging solve.sh doesn't stall the pipeline.
- *Not yet:* the 5-run band eval (Part 2), resume after a kill and safe concurrent runs (Part 4).

**Follow-ups in the same step:**
- *argparse CLI.* `generate.py` now has a `main()` built on stdlib `argparse`: an optional `topic` (same default as before) and `-o/--output-dir`, plus `--help`. It exits 0 when the task passes and 1 when it fails, so batch scripts can rely on it. `requirements.txt` is unchanged on purpose: argparse is stdlib, and the PyPI `argparse` package is an obsolete backport that can shadow it.
- *Repair prompts see pytest's output, not install noise.* `test.sh` prints about 3,000 chars of apt/uv output before pytest starts, and the repair error kept only the last 5,000 chars, so a long failure could be cut off. `checks._pytest_excerpt()` now starts at pytest's `test session starts` line, and falls back to the plain tail when pytest never ran (for example an apt failure). On the real SQLite failure, the excerpt went from 5,018 chars of mostly noise to 2,837 chars of pure pytest output.

**Results:** 4 topics (C build, SQLite migration, nginx proxy, Pillow upgrade) → 4 valid, correct tasks in `output/`. 3 needed one repair round, and every repair fixed a real defect without weakening the tests. Totals: about 30k input and 182k output tokens. An independent `harbor run` re-check gave oracle 1 and nop 0 for each task. Details are in `.claude/logs/2026-10-21-part1-generator-test.md`.

**Lessons for Part 2 prompts:** two of the three repairs were bugs in how the tests talk to the container, not in the task itself. In one, tests called `python3` and got the verifier's uv Python instead of the image's. In the other, a test didn't handle sqlite3 printing nothing for an empty `-json` result. Separately, Harbor replaces the Dockerfile `CMD` with `sleep infinity`, so services don't start on their own, and one instruction wrongly implied they do. All of this belongs in `HARBOR_CONTRACT`.

## 2026-10-21: Part 2 band eval, triage and calibration

**What:** the pipeline now measures difficulty and only keeps learnable, fair tasks.
```
generate_task (Part 1: valid, solvable, meaningful)
 → band eval: 5 × terminus-2 + glm-5.3-flash (reasoning_effort=high)
      0/5 too_hard · 1-3/5 learnable · 4-5/5 too_easy · <5 valid runs → inconclusive
 → triage (learnable only): glm-5.1 labels each failed run model_fault or task_fault
 → keep ⇔ learnable AND every failure is the model's fault
```
- `generator/evaluate.py` (new): `run_band()` (runs, classification, top-up of invalid runs, verdict, tokens/cost) and `triage()` (failing tests + the last 15 agent steps from `trajectory.json` → glm-5.1 → fault/category/reason).
- `generator/pipeline.py` (new), plus `scripts/pipeline.sh`: `--topics FILE`, `--eval-only TASK…` and `--smoke TASK`.
  - Kept tasks stay in `output/<task>/` with a `band.json`.
  - Rejected tasks move to `output/_rejected/<task>/`.
  - Each batch writes `output/_reports/<batch>.md` and `.json`, with a pass histogram, per-task verdicts and the reasons.
- `generator/prompts.py`:
  - three Harbor runtime facts added to `HARBOR_CONTRACT`;
  - a difficulty target added to `QUALITY_RULES`;
  - a calibration block for the spec prompt;
  - the triage prompt.
- `generator/checks.py`: `harbor_run()` factored out, so the oracle/nop checks and the band eval share one subprocess wrapper.
- `generator/config.py`: new settings `EVAL_CONCURRENCY` (5), `MAX_INVALID_RERUNS` (3), `CALIBRATION_WINDOW` (8), `REJECTED_DIR`, `REPORTS_DIR` and `CALIBRATION_FILE`.
- `scripts/topics.txt`: 12 hand-written topics across 12 categories.

**Decisions (chosen vs. alternative, and why):**
- *Topics: hand-written list vs. glm-5.1 ideation.* **Hand-written.**
  - Diversity is graded, and with a list the category spread is visible and fixable before any money is spent.
  - LLMs asked for "diverse tasks" drift to the same favourites (Docker, git, nginx), so ideation would need dedup logic and its own prompt tuning.
  - Whether a task lands in the band depends on how glm-5.1 *expands* the topic, not on who wrote it, so automating topics doesn't raise yield.
  - A fixed file also gives reproducible before/after comparisons.
  - Ideation wins at scale (100+ tasks) and is a later step.
  - Note: the Part 1 topics were also written by hand, by Claude. glm-5.1 only expands topics into specs.
- *Timeouts and infra errors: invalid + re-run vs. counting them as failures.* **Invalid + re-run, max 3 extra; otherwise `inconclusive`.**
  - The README says timeouts don't count as the model failing.
  - An agent timeout that still scored 1 is also invalid, because a run that never finished didn't cleanly solve the task.
  - The cap bounds cost on tasks that time out every time. Those are effectively too slow and get rejected.
- *Failure reasons: glm-5.1 triage vs. rules only.* **glm-5.1 triage.**
  - "Which test failed" isn't a reason. The README requires knowing why each shipped task fails, and that a failure is the model's fault.
  - Only an LLM reading the trajectory can tell "agent misdiagnosed" from "instruction was ambiguous".
  - It runs only on learnable tasks (the only ones shipped), to keep cost down.
  - The prompt makes the model name a concrete flaw before it may blame the task.
  - glm-5.1 is the authoring model, so no extra model is introduced.
- *Steering: filter + calibration vs. filter only vs. per-task tuning.* **Filter + calibration.**
  - Filtering alone leaves yield to luck.
  - Calibration feeds the last 8 verdicts (for example "5/5 too_easy: single UPDATE fix") into the next spec prompt, which is cheap.
  - Rewriting individual tasks is stretch goal A and is left out.
- *Smoke test: once vs. per task vs. never.* **Once, before any 5-run eval.**
  - One run can't place a task in the band: a pass fits 1/5–5/5, and a fail fits 0/5–4/5.
  - Part 1 already proves each task works.
  - The one real risk is the eval config itself. Harbor passes `reasoning_effort` to litellm with `drop_params=True`, which can drop it silently, and cost may come back null. One run checks both before money is spent on 5 × N.
- *Order of gates: cheapest first.* Validator (free) → oracle and nop (Docker) → band eval (paid) → triage (paid, learnable only). Each gate stops a broken task before the next, more expensive one.
- *`evaluate.py` as its own module vs. part of `checks.py`.* `checks.py` answers "is the task correct?" and is cheap and deterministic. `evaluate.py` answers "is it the right difficulty?" and is paid and slow. Keeping them apart keeps Part 1's checks simple. `--eval-only` reuses the eval without generation.
- *HARBOR_CONTRACT fix folded into Part 2* rather than committed on its own. These facts came from Part 1 repairs: the verifier's `python3` is uv's; `CMD` never runs because Harbor uses `sleep infinity`; commands can print empty output. They are tested together with calibration by the first fresh Part 2 generation.

### Part 2 first results and an A/B control run

**Baseline band eval (the 4 Part 1 tasks, built before the difficulty lever existed):** all 4 were **too_easy, 5/5**, and all were moved to `output/_rejected/`.
- The agent solved every run in 4–9 steps and 1–3 minutes (each run is allowed an hour).
- 20 runs, 0 invalid, $0.05 of eval cost.
- One-time smoke test beforehand: 1 run passed in 6 steps. It showed reasoning on every step, the right model (`z-ai/glm-5.3-flash`), and a reported cost of about $0.002 per run.

**Control run (matched A/B).** The next generation is the first one to use the difficulty rule and calibration. To tell whether those levers cause any change, topic #1 of `scripts/topics.txt` is generated twice:
- **treatment:** the current prompts plus calibration;
- **control:** `pipeline.py --control`, which uses the same prompts minus `DIFFICULTY_RULE`, with no calibration block.

Both arms keep the Harbor runtime facts, which are correctness fixes, not difficulty levers. Control results are reported with an `arm` column but kept out of the calibration history, so they don't steer later designs. Treatment also runs topic #2.

- *Why a control:* the new topics differ from the Part 1 topics in two ways at once. The prompts are new, and several topics were written with more than one root cause built in. Without a matched control, a change in the band couldn't be credited to the prompts rather than the topic wording.
- *Why matched (same topic):* a control on a different topic would mix the same two factors again.
- *Limit:* one task per arm is a directional signal, not proof. Generation is noisy, and the same topic and prompt can give tasks of different difficulty. A firmer answer needs several pairs, for example within the 10+ task batch.
- *Code:* the rule is now a separate constant, `prompts.DIFFICULTY_RULE`. `prompts.SYSTEMS` holds the treatment prompts and `prompts.CONTROL_SYSTEMS` the control ones. `generate_task(control=...)` chooses between them, and `pipeline.py --control` sets it.

**Control-run result (CMake topic):** both arms were **too_easy, 5/5**.
- **Treatment** (`cmake-visibility-plugin-crash`): it did add a second fault, but both faults were one-line edits (a macro-name typo and a missing export attribute). Runs took 6–7 steps but 11–25 minutes each, because glm-5.3-flash thought longer per step. The task was harder to reason about but no harder to solve.
- **Control** (`cmake-shared-lib-abi-mismatch`): 1 fault (a PRIVATE compile define), 4–8 steps.

Conclusion: the difficulty rule changed designs on paper only. Directional, n=1.

**Stopped early:** treatment topic #2 (SQLite NULL/timezone) was stopped by the user after its spec call, to save time. Its partial log is in `output/_logs/a-postgresql-style-*`. No files or eval were produced.

## 2026-10-21: Difficulty knobs (deep dive) and gates

**Why:** all 6 evaluated tasks were too_easy (5/5). We needed to know what makes a task hard before building more.

**Evidence** from 12 trajectories (2 per task) and the 6 human-made examples:
- The agent found the root cause within its first 1–3 command turns in every trial. The new found-turn metric confirms it: the agent touched the faulty file on turn 1 in 14 of 15 runs of the build tasks.
- There was 1 real backtrack in 12 trials, on the only task with interacting faults.
- Environments were 2–14 files and 77–303 lines, so one `cat` showed everything.
- Fixes were 1–4 lines. The instructions named the faulty file (`migrate_v2.sh`, the nginx config, `Makefile`, `types.h`), error messages named the fault, and expected outputs were pasted into instructions.
- 4 of 6 tasks were textbook bugs.
- The harder human examples state a goal rather than a located symptom, use real or large code and data, demand precision across many records, or require building something.

**Knob catalogue** (full version in the plan; in short):
- **A. Discovery:** instruction specificity, search-space size, decoys.
- **B. Diagnosis:** symptom directness, observability, familiarity/recall.
- **C. Depth:** fault count, chaining, cross-layer, fixes that compound.
- **D. Execution:** fix size, precision over volume, data recoverability, long-running steps.
- **E. Verification:** leaked outputs, hidden edge cases, self-check traps.
- **F. Ambiguity:** only when the environment resolves it.

Each knob is paired with a fairness guard, because failures must be the model's fault.

**What was built:**
- `prompts.DIFFICULTY_RULE` was rewritten as knob guidance, with bad and good examples from our own tasks.
- `prompts.DIFFICULTY_SPEC_FIELDS`: the spec must commit to `faults[{layer, where, what, symptom, how_discovered, depends_on}]`, `decoys`, `hidden_edge_cases`, `why_not_textbook` and `expected_agent_steps`.
- New `generator/difficulty.py`, with gates enforced in code before any Docker or eval spend:
  - **spec gate:** at least 3 faults, in at least 2 layers, at least 1 `depends_on` chain, no fault repeated in one place, at least 1 decoy, at least 1 hidden edge case;
  - **files gate:** the instruction must not name shipped source/config files (input data and output files are fine); environment/ must have at least 1,000 non-blank lines; solve.sh must have at least 15 meaningful lines; at most 2 test literals may appear in the instruction.

  On the 6 old tasks, every one fails at least 2 gates.
- **Spec critic:** one glm-5.1 red-team call walks through how a strong agent would solve the spec and rewrites it if any fault would fall within 3 commands. The revised spec is used only if it passes the gate.
- **Trajectory metrics:** `median_steps` and `median_found_step` per task go into the calibration notes, for example "agent median 7 steps, reached the faulty files on turn 1".
- Settings: `MIN_FAULTS`, `MIN_FAULT_LAYERS`, `MIN_ENV_LINES`, `MIN_SOLVE_LINES`, `MAX_LEAKED_LITERALS`, `SPEC_CRITIC` and `MAX_SPEC_ATTEMPTS`.

**Bug fix found along the way:** terminus-2 stores the agent's shell commands in `tool_calls`, not in `message`. Triage was only reading `message`, so glm-5.1 would have judged failed runs without seeing what the agent typed. `trajectory_tail()` and the found-turn metric now include the commands.

**Decisions:**
- *Deep dive before more code* (the user's call) rather than picking levers from intuition. The evidence pointed to discovery and depth, not "think harder".
- *Implement A1+E1, C1–C3, A2+A3, B1+E2 and B3 now; defer D2–D4 and F1.* The chosen knobs had the most evidence, are cheap, can be enforced in code, and are low-risk for fairness. D2–D4 (big data, long builds) cost more time per run. F1 (ambiguity) carries the highest fairness risk.
- *Gates in code plus a critic, rather than prompt wording alone.* The CMake A/B showed that wording changes designs only on paper. The gates are free and objective. The critic adds an "agent's-eye" check that the gates can't do, for about one extra spec call.
- *Instruction leak rule: shipped code/config files only.* The first version missed `migrate_v2.sh` (solve.sh changes the database, not the script) and nginx's renamed COPY destination. It also flagged the English word "default" and input data files such as `sample.csv`. The rule now checks `COPY` destinations and code/config extensions, and skips data files and bare words.
- *Control arm extended:* `--control` now also removes the spec profile fields and skips the gates and the critic, so the A/B isolates every difficulty lever. The Harbor facts stay in both arms.

## 2026-10-21: Persistent, self-tuning difficulty config

**What:** the difficulty gate values are no longer hard-coded guesses. They live in `generator/difficulty.toml` (committed, hand-editable), and `scripts/tune.sh` (`generator/tune.py`) searches for the level that puts tasks in the band, then saves it there.

- **One dial.** `level` scales every knob: `clamp(round(base × level), floor, ceiling)`. `max_leaked_literals` tightens the other way (`base / level`, floor 0).
  - The `[base]` values are the starting values chosen earlier, just past what the 6 too-easy tasks had.
  - The `[ceiling]` values are where a knob stops adding difficulty or can't be built: faults 6, layers 4, env lines 4,000, solve lines 60, critic threshold 8.
  - `config.py` now derives `MIN_FAULTS` etc. from the file. Precedence is env var, then file, then defaults. The prompts and the critic quote the live values; at level 2 the prompt asks for 6 faults and about 2,000 lines.
- **The search:**
  - A probe is 3 tasks at one level, generated and band-evaluated in parallel, with topics rotated from `topics.txt`.
  - Its verdict comes from the majority of the 3 tasks: too_easy (4–5/5), too_hard (0/5, or glm-5.1 couldn't build the task), or in_band (1–3/5).
  - The level doubles while probes are too easy, up to 4, where every knob reaches its ceiling. Then it bisects between the brackets. It stops in band, when the step drops below 0.25, or after 2 bisections.
  - **Saturation stop:** if a doubling doesn't lower the pass rate, doesn't move the found-turn by at least 1, and adds less than 20% steps, the dial is saturated. The search stops and says the next levers are D2–D4 or trajectory hardening.
  - Worst case: 5 probes, 15 tasks, about $7.
- **Persistence and warm start:**
  - The result is written back to `difficulty.toml`: level, brackets, status and timestamp. The file is rewritten from a template, so comments and hand edits to `[base]`/`[ceiling]` survive.
  - Every probe is appended to `output/_logs/tuning.jsonl`, and each run writes a report to `output/_reports/tune-*.md`.
  - A tuned config later costs **1 check probe**. If that probe has drifted, the search runs inside the saved brackets.
  - Every evaluated task, from tuning or from normal pipeline runs, is logged in `calibration.jsonl` with its level, actual features (env lines, solve lines, faults, layers), median steps and found-turn. Generation failures are logged too. The tuner reuses any level that already has 3 logged tasks, for free.
- **Ablation:** `tune.sh --ablate` resets one numeric knob at a time to its base value at the saved level (4 probes) to show which knobs matter. Run on request only.
- **Critic fix:** the dry run showed the critic's revised spec dropping the difficulty profile whenever the input spec lacked it. `CRITIC_SYSTEM` now includes the profile schema and requires it.
- `pipeline.py` gained `--batch-id`, so the tuner can find each probe's results, and it logs generation failures as tuner evidence; calibration prompts still use only evaluated tasks. Each probe runs its 3 tasks' evals 3 at a time (9 containers at most), because Docker has 8 GB of memory.

**Decisions:**
- *Measure the values by search instead of guessing* (your proposal): double until too hard, then bisect.
- *Bounded doubling: ceilings and a saturation stop* (your point that doubling forever is pointless). Each knob has a ceiling beyond which more stops mattering or can't be built. Faults and layers already reach theirs at level 2, so at most 2 doublings are ever possible. The saturation rule stops early once a doubling changes nothing measurable.
- *One dial vs. a separate binary search per knob.* One dial costs about log(range) ≈ 3–5 probes. Per-knob search costs k × log ≈ 8–12, and its results depend on the order you tune in, because the knobs interact (a bigger environment only matters if the instruction doesn't name the file). A single knob's small effect also drowns in noise with 3 tasks per probe. Per-knob attribution comes from **leave-one-out ablation** (k = 4 probes, only when needed) and from the features logged on every task.
- *3 tasks per probe, judged by majority.* Generation is noisy (the CMake A/B), so a single task could send the search the wrong way. 3 is the smallest number with a majority.
- *A task glm-5.1 can't build counts as too hard.* At high levels "too hard" can mean "can't be generated" rather than 0/5. Both mean step down.
- *Persistent editable config with a warm start* (your request). The first run pays for the search; later runs start from the saved level and usually need one check probe. TOML, because it's readable and editable and `tomllib` is in the standard library. Writing uses a fixed template, so no new package (such as `tomlkit`) is needed.
- *Level-dependent prompt text.* The model sees the real targets ("at least 6 faults"), not fixed numbers, so the gate and the prompt never disagree.

**Offline verification** (simulated probes; no spend):
- easy → easy → hard → band gives levels 1 → 2 → 4 → 3 and saves level 3 with brackets 2 and 4;
- a flat doubling is saturated after 2 probes;
- generation failures count as too hard (1 → 0.5 → 0.75);
- a warm start costs 1 check probe, and drift re-searches inside the brackets;
- logged evidence is reused for free;
- hand edits and comments survive a save;
- the real dry run plans 1 probe at level 1 and doesn't touch the file;
- the Part 2 regression and control suites still pass.

### Speed-ups: early stops (no change to any verdict)
**Why:** a probe took about 1.5–2 hours. glm-5.1 makes 5–7 sequential calls per task at 6–8 minutes each. The bigger tasks needed for difficulty add repair rounds and slower agent runs. Docker's 8 GB forces evals to 3 at a time. And a probe waited for its slowest task.

- **Band-eval early stop** (`evaluate.run_band`, `checks.harbor_run(stop_when=...)`):
  - Harbor's job folder is polled every 15 s. Once BAND_HIGH+1 = 4 valid passes exist, the verdict is too_easy whatever the remaining runs do, so the job is stopped and its unfinished trials' containers are removed.
  - The report shows "too_easy (stopped early after 4 passes)", and the histogram counts it at the passes it reached.
  - Learnable tasks always get all 5 runs, because the shipped pass count must be exact.
- **Probe majority early stop** (`tune.run_probe`): the 3 pipelines are watched. Once 2 tasks agree, the third is stopped: its process tree is killed, its containers are removed, and its unevaluated task folder moves into its log folder (`unevaluated-task/`). It's recorded as `skipped`.
- `checks.kill_tree()` and `checks.remove_containers()` are shared helpers. `harbor_run` now polls a `Popen` instead of blocking, which the normal oracle/nop checks use too; those were re-verified on the known-good fake task (oracle 1, nop 0).
- *Decision:* these two speed-ups were chosen over running the next level speculatively (more spend and Docker load) and raising Docker's memory (a machine setting on the user's side). Neither early stop can change a result.
- *Tested offline* with a fake Harbor and a fake pipeline:
  - the band eval stopped at 4/4 after 25 s, where the hanging 5th run would have taken 10 minutes;
  - the probe stopped after 2 too-easy tasks in 30 s, and the slow 3rd was skipped;
  - no leftover processes;
  - the regression suites still pass. One test fake was updated for the new `stop_when` argument.
- *Rollout:* tuning probe 1 was already running with the old code. A watcher restarts the tuner as soon as probe 1's verdict is logged. The restarted tuner reuses probe 1's 3 logged results at level 1 as free evidence. The first version of the watcher used `pkill -f "tune.py"`, which would have matched and killed the watcher itself (its own command line contains that text). It was replaced before it fired, with one that targets Python processes by PID. (Superseded: the watcher was never needed; probe 1 was restarted by hand. See "Tuning runs" below.)
- *Parser robustness (found live in tuning probe 1):* the CMake task's critic reply (6 minutes, 25k tokens) was rejected because glm-5.1 returned `failure_modes` as a list, not a string. `Spec` now accepts the shapes glm-5.1 actually uses, through pydantic `field_validator`s: lists are joined into text for prose fields, a single string becomes a list where one is expected, and ranges like "15-25" become a number. The content is unchanged and the gates still check substance. This avoids re-paying a full call, or losing the critic's hardening, over a format detail. It applies to new processes only; the running probe retried the critic.
### Tuning runs (probe 1 restarts)
- *Probe 1 restarted (15:54) to pick up the fixes.* The first run of probe 1 was killed 33 minutes in, to switch to the new code (parser fix, both early stops, live call logging). Nothing had been evaluated. In that run:
  - **DNS** (6 faults, 3 layers, ~25 expected steps) ended as a **generation failure**: gate fail, then Docker build fail, then oracle 0 twice, after 3 repairs;
  - **SQL** (4 faults) was in its first gate repair;
  - **CMake** had lost about 15 minutes to two critic replies rejected for list formatting, the bug fixed above.

  Partial logs are kept in `output/_logs/` (the DNS task in `last-attempt/`). The early signal: at level 1 the designs are already hard for glm-5.1 to *build*.
- *Probe 1 stopped again (15:58),* 4 minutes after the restart and still in the spec stage, to review the topic list first. Nothing was evaluated, `difficulty.toml` is unchanged (level 1, untuned), and `tuning.jsonl` has no probe entries. Partial logs are in `output/_logs/*-20261021-155447`.
- *Probe 1 started again (16:05)* on the updated topic list (the DNS topic replaced, see below), with all fixes active.

### DNS topic discarded (`scripts/topics.txt`)
- **Removed:** "a local DNS and service setup where a client intermittently hits the wrong backend because of a stale hosts entry and a misconfigured resolver order".
- **Why:** the scenario only works by editing `/etc/hosts` and the resolver config, and inside a Harbor/Docker container Docker controls those files. It bind-mounts them, so they can't be replaced (`sed -i`/`mv` fail with "Device or resource busy") and may be reset. The one attempt (tuning probe 1, first run) failed to build after 3 repairs. Its reference solution crashed on exactly this, then still failed the tests.
- **Replaced with:** "a static-site build pipeline (templates, includes, asset hashing) that produces subtly wrong output pages: broken internal links, stale asset references and wrong page ordering". It's deterministic and self-contained in one container, and it fills a category not otherwise covered.
- *Decision:* replace the topic rather than teach the prompts a Docker `/etc/hosts` rule. That keeps the prompts unchanged during tuning, and the networking scenario offered nothing the other topics need. The other 11 topics are unchanged.

### Spec gate: "repeated fault" rule fixed (mid-tuning, applies from probe 2)
**Problem found live (probe 1, SQL topic):** the first design, `sqlite-null-tz-analytics-report`, had 5 faults, 6 decoys and 5 edge cases. The gate rejected it for two reasons:
- **Fair:** "faults must span at least 2 layers" (all 5 were labelled `code`).
- **False positive:** "faults must be in different places, not one fault repeated". The old rule compared only the `where` text, and two pairs of faults shared a SQL view (`v_daily_revenue` ×2, `v_daily_sessions` ×2). They were 4 *different* bugs: UTC-day grouping, integer division, a NULL timezone offset, and a `COALESCE` skew. The rule was meant to stop the Pillow pattern (the same `sed` in 4 files), not several real bugs in one place.

**Why fix it mid-tuning:** a false rejection can end as a generation failure, and the tuner counts that as "too hard". The search could then step the level *down* because of a gate bug rather than real difficulty. It also wastes a re-spec (about 7 minutes and 30k tokens) each time.

**Change (`generator/difficulty.py`, `spec_gate`):**
- **A repeat now means the same kind of bug.** Two faults whose `what` descriptions share at least 80% of their words (Jaccard) count as the same fix repeated.
- **New rule:** the faults must touch **at least 2 different files**. The file is the path part of `where`. This keeps the original intent, that the agent has to search more than one place.
- **Unchanged:** the layer rule. Its complaint about this design was fair. (The layer labels are self-reported by glm-5.1, a softer weakness left for later.)

**Tested offline:**
- the real SQL spec now gets only the fair layer complaint;
- a Pillow-style spec (the same fix ×4) is still rejected;
- 3 different bugs in 1 file is rejected by the new file rule;
- the good fixture passes;
- the Part 2 regression suite passes.

**Confound, noted for the tuning results:** probe 1's pipelines already had the old gate loaded, so probe 1 runs under the stricter gate and probe 2 onward under the corrected one. The difference can only *reduce* false generation failures later, so it cannot make probe 1 look easier than it was.

### Lenient JSON parsing (mid-tuning, applies from probe 2)
**Problem found live (probe 1, SQL topic):** the critic's first reply (8.5 minutes, 35k tokens) was rejected as invalid JSON. The cause was a **single trailing comma** (`…issue.",` followed by `}`) at character 20,895 of an otherwise valid reply. A retry succeeded, but the first reply's cost was lost. This is a second format failure, after the list-vs-string one fixed earlier.

**Change (`generator/llm.py`):** `parse_json_object` first tries strict JSON (with `strict=False`, so control characters are allowed inside strings). If that fails, it tries again after `_relax_json()`, which removes trailing commas (`,}` / `,]`) and `//` or `/* */` comments **outside string literals**. It walks the text character by character, so commas, slashes and escaped quotes inside strings are untouched. Genuinely broken JSON, such as a missing comma between keys, is still rejected and retried.

**Tested:**
- the real failed critic reply now parses, and its revised spec (`sqlite-null-tz-revenue-report`) passes the spec gate;
- trailing commas and comments are removed;
- `"http://x.io/a,}"` and escaped quotes inside strings are kept;
- real breakage is still rejected;
- the Part 2 regression suite passes.

*Decision:* repair the common, unambiguous slips rather than add a full JSON5 parser (a new dependency) or ask the model again. This fits the earlier choice to normalise format rather than re-pay 6–9 minute calls.

### Instruction review: requirements and symptoms, never a diagnosis (mid-tuning, applies from probe 2)
**Why:** the file writer can slip and explain *why* something is broken in `instruction.md`, which lets the agent skip the investigation. The leak gate only catches file names and pasted test values, not a diagnosis written in prose.

**Changes:**
1. **Prompt (`prompts.DIFFICULTY_RULE`):** the "symptom, not location" rule now separates a **requirement** (what must be true), a **symptom** (what the user sees) and a **diagnosis** (why it's broken, forbidden). The example is an inventory report: requirement "stock_report.csv must list every warehouse with its total units on hand"; symptom "two warehouses are missing and several totals are lower than the inventory counts"; forbidden diagnosis "the join drops warehouses whose IDs have trailing spaces…". It's part of the difficulty rule, so the control arm doesn't get it.
2. **Instruction review (`generate.review_instruction`, `prompts.INSTRUCTION_REVIEW_SYSTEM`):** after the files are written, and again whenever a repair changes `instruction.md`, one short glm-5.1 call gets only the instruction, the spec's hidden faults and the tests.
   - It replies `VERDICT: clean`, or `VERDICT: leaks` with each leaking sentence and the fault it reveals, plus a rewritten instruction.
   - The rewrite replaces `instruction.md` directly, without using a repair round. It must keep every requirement, path and format the tests rely on.
   - It runs before the difficulty gate and Docker. It's skipped for the control arm, and it's best effort: on a model error the instruction is kept.
   - Setting: `INSTRUCTION_REVIEW`. The dashboard shows it as stage "3b instruction review".

**Tested:**
- offline: the reply parser handles clean, leaks and malformed replies; the hook swaps only `instruction.md`.
- **Live, on the static-site task** (`petrify-static-site-broken-output`):
  - **Real instruction → `clean`** (9 s, 483 tokens). On review that was the right call: the sentence that prompted this ("only the hashed versions exist… the HTML points to the unhashed originals") describes what anyone sees in `dist/`. The real fault is `rel_path_key()` in `petrify/utils.py` computing asset-map keys from the wrong directory, and the sentence doesn't reveal it. **The original concern was overstated.**
  - **Control: the same instruction with a planted diagnosis** ("…because rel_path_key() in petrify/utils.py builds the asset-map keys relative to the working directory") → `leaks` (10 s, 747 tokens). It named fault 2 (location and mechanism), removed the clause, kept the symptom, and kept every requirement line (`feed.xml`, 8-character hex hashes, `<nav>`).

*Decision:* sharper prompt wording plus a cheap meaning-level review, rather than a word-overlap check in code (too noisy: requirements legitimately share words such as "hash" with the faults) or leaving it to the band eval (a full build and eval spent to learn it).

### Large tasks written in parts, cut-off replies made visible (mid-tuning, applies from probe 2)
**Problem found live (probe 1, CMake topic):** the files reply took 16 minutes and 69k output tokens, but only about 24k characters of it were visible text. It contained 5 files: `instruction.md`, the Dockerfile, `solve.sh`, a 267-line test file and a 16-line `CMakeLists.txt`. The Dockerfile `COPY`s `src/`, `audiomix.map`, `Makefile` and `README.md`, which were **never written**. The difficulty gate reported "environment/ has 33 non-blank lines; needs at least 1000". That was true, but it was the wrong explanation: the project was missing, and the Docker build would have failed anyway. The likely cause is that about 62k tokens of hidden reasoning used up the output budget, so the reply ended early. It couldn't be confirmed, because the finish reason wasn't logged.

**Changes:**
1. **Finish reason logged (`llm.chat`):** every call's usage now includes the API's `finish_reason`. `"length"` means the reply was cut off at the output limit; `"stop"` means the model finished on its own. So a cut-off reply shows up as cut-off, not as a puzzling gate failure. *Verified live:* a tiny call logged `finish_reason: "stop"`.
2. **Missing-COPY-source check (`generate.missing_copy_sources`):** before the gates and Docker, every `COPY`/`ADD` source in the Dockerfile must have been written. A missing one is reported precisely ("environment/src (the Dockerfile COPYs it, but it was never written)") and goes to the repair loop. It handles the JSON form, wildcards and `--chown`, and skips URLs, `--from` and whole-context copies. It applies to **both A/B arms**, because it's about correctness, not difficulty. *Verified on the real CMake reply:* it finds exactly `src`, `audiomix.map`, `Makefile` and `README.md`.
3. **Files written in parts (`generate.write_project`, `prompts.PROJECT_SYSTEM`):**
   - The old single "files" reply had to hold the whole task.
   - **Step 3a, project:** glm-5.1 first lists a **manifest** of every environment file, then writes them (not the Dockerfile).
   - Manifest files that a cut-off reply left out, or left incomplete, are requested in up to **2 continuation calls**.
   - **Step 3c, core files:** `instruction.md`, the Dockerfile, `solve.sh` and the tests are written **against the real project code**, which is included in the prompt up to 150k characters, beyond that listed by name.

   *Verified offline:* a first reply with 1 of 3 manifest files complete leads to 1 continuation call, and all 3 files end up present. The dashboard shows stages "3a writing project" and "3c writing core files".

**Tested:**
- the Part 2 regression suite and the control-arm suite pass (both arms have the new project step; the control still drops only the difficulty rule and profile fields);
- all modules import.

**Trade-off:** one more model call per task, but each reply is smaller and less likely to be cut off. The tests and solution are written against code that already exists, rather than both being imagined in one go.

### Probe 1 result (level 1) and manual step to level 2 (16:54)
**Probe 1 at level 1 was stopped by the user once the verdict was clear, and recorded by hand** in `output/_logs/tuning.jsonl` (`"source": "manual"`):
- **SQL** (`sqlite-null-tz-revenue-report`, 4 faults): **too_easy**. The band eval stopped early after 4 passes, the first live use of the early stop. Runs took 16–26 agent steps and 2–4 minutes each.
- **Static site** (`petrify-static-site-broken-output`, 5 faults, ~28 expected steps): **3 of 3 passed** (20–25 steps, 4–6 minutes). The 2 running agents had already identified all 5 planted faults when it was stopped. On track for too_easy.
- **CMake** (`cmake-shared-lib-abi-crash`): **not built**. Its files reply was cut off (the project was missing) and it was stopped during repair 1.

The half-evaluated or unbuilt task folders moved from `output/` into their log folders (`unevaluated-task/`).

**Reading:** level 1 roughly **tripled** the agent's work (4–9 steps before, 16–29 now) but didn't change the outcome. glm-5.3-flash at high reasoning reads every module and fixes faults one by one, so more faults and more code mean more steps, not failures. The found-turn metric is too blunt here: every run "touches" the faulty files on turn 2, because the agent reads many files early. It measures when a file is *read*, not when the bug is *understood*.

**Manual step:** `difficulty.toml` set to **level 2.0** (`bracket_low = 1.0`, status still untuned), the doubling the search would have made itself. Level-2 knobs: at least 6 faults, at least 4 layers, about 2,000 env lines, a solve.sh of at least 30 lines, at most 1 leaked literal, critic threshold 6 commands. The tuner was restarted from that level. Probe 2 reuses probe 1's topics, because the manual record doesn't advance the topic rotation. That gives a cleaner comparison of the same topics at double difficulty. All the fixes since probe 1 apply: parser robustness, lenient JSON, the gate's repeat rule, the instruction review, finish-reason logging, the COPY-source check and two-part file writing.

**Watch-out:** if level 2 is also too easy at similar step counts, the saturation rule stops the search. That would mean faults and size aren't the lever for this agent, and the parked alternatives (trajectory hardening; precision, recovery or build-from-goal task types) become the next move.

## 2026-10-21 (evening): New difficulty scale, spaced discovery, hidden design, problem-not-guide instructions
Probe 2 (level 2, 6 faults) was stopped by the user at its first design call to switch to these changes. Nothing was built. All of them apply to the next probe.

### Knob values set by the user (`generator/difficulty.toml`)
- **Faults: at least 10** (base 10, ceiling 10). **Critic found-within: 10 steps** (base and ceiling 10). Level reset to 1.0 and tuning to `untuned`: the earlier level numbers meant different knobs.
- *Decision:* the user's values were taken over my suggestion (6 faults base, ceiling 10; found-within 8; let probe 2 finish first).
  - The case for them: compounding. With a 10% miss rate per fault, 3 faults pass about 73% of the time, but 10 faults pass about 35%.
  - The risks I raised: glm-5.1 may not build 10-fault tasks reliably (a 6-fault DNS design and a 3-fault CMake reply already failed to build). Turn-based rules can only be enforced on paper. Hiding 10 faults may tempt unfair designs.

### Spaced discovery, graded by the critic (`difficulty.discovery_eval`, `[discovery]` in `difficulty.toml`)
- Every fault gets a `discovered_at_step` estimate (the agent step at which it would be found), from the spec and the critic.
- The 9 gaps between consecutive finds are graded:
  - **too easy, rejected by the spec gate:** a first find before step 10, or any gap below 2 (two faults falling to the same look);
  - otherwise graded by the **median gap**: 2 to under 3 moderate, 3 to under 5 **hard** (target about 4), 5 to 6 **very hard**, above 6 **too hard** (**flagged, not rejected**, as the user asked);
  - **horizon** (the last find) above 50 steps is flagged as a **timeout risk**: at 1–5 minutes per step on hard tasks, 46–64 steps can reach the 1-hour agent limit, and timeouts count as invalid, not failures.
- The critic prompt states the bands and must put its estimates in the revised spec. The grade is logged as a `discovery_eval` event and shown in a new dashboard column "critic eval", e.g. `hard · median gap 4 · min gap 4 · first at step 10 · ~46 steps`.
- *Decisions:* any short gap rejects, because one burst is exactly the level-1 pattern. The median grades, so one long gap can't inflate the grade. The bands are not scaled by the level.
- *Tested offline:* a burst, a first find too early and missing estimates are rejected; gaps of 2, 4, 6 and 8 grade moderate, hard, very hard and too hard, with timeout risk from horizon 64.

### The difficulty eval is never visible to the solving agent
- **Where the eval lives:** only in the logs (`output/_logs/`: spec, `critic.json`, `discovery_eval` events). It's outside the task folder.
- **What the agent sees:** only `instruction.md` and the image built from `environment/`. `tests/` and `solution/` arrive only at verification, and `task.toml` and `band.json` are never in the image.
- **The remaining risk:** the file writer copying design details into task files. Two defences:
  - New **`difficulty.meta_leaks`** check, in both arms. It scans `instruction.md` and `environment/` with word-boundary patterns for fault numbers, `discovered_at_step` and other spec keys, "decoy" or "red herring" labels, and "intentional", "planted" or "injected" bug comments. Hits go to the repair loop.
  - A matching rule in `QUALITY_RULES` ("faulty code must look like ordinary code written by a developer who made mistakes").
- **Real leak found:** the DNS task's last attempt had `# --- Monitoring (decoys) ---` and `# Error log (decoy - contains misleading errors...)` in `environment/setup.py`.
- *Tested:* planted markers are caught. `DEFAULT 0`, "critical" and test files aren't flagged.

### Evidence reuse tied to exact knob values (`pipeline.KNOBS`, `tune.evidence`)
Calibration rows now record the knob values used. The tuner reuses a level's logged results only when the knobs match, because a `[base]`/`[ceiling]` edit changes what "level 1" means. Old-scale rows without knobs are no longer counted. *Tested:* the tuner simulation passes, including evidence reuse with matching knobs.

### Instructions: a problem, not a guide
**Why:** all 8 solved-task instructions guided the agent instead of posing a problem:
1. a numbered symptom per fault (it learns the count and where each lives);
2. the fault categories ("currency, eligibility, timezone, and refund handling");
3. pointers to the answers ("consult docs/", "inspect migrate_v2.sh");
4. exact expected outputs (nginx JSON, "≈ 0.577350"), which give a perfect self-check;
5. the test list ("Verification will confirm: 1… 4…");
6. narrowed scope or a progress check ("only change the Makefile", "run pytest -v").

**Comparison with `examples/`:** length doesn't predict difficulty (fix-git, 30 words, is easy; fix-code-vulnerability, 575 words with heavy hints, is labelled hard). The examples spend their detail on the **deliverable** (log-summary gives a full CSV layout with `<count>` placeholders, never the counts), not on what's broken. *Caveat:* the example labels are the authors' judgments, not measured pass rates.

**Changes:**
- `DIFFICULTY_RULE`: a "problem, not a guide" bullet. Detail is allowed only about the deliverable; the 6 patterns are forbidden.
- **`INSTRUCTION_REVIEW_SYSTEM` extended** from diagnoses only to all 8 violation types. It rewrites the instruction as a problem statement plus the deliverable spec, keeping everything the tests need.

**Live test** on probe 1's instructions:
- **Static site:** the 3 numbered per-fault symptoms and "has several problems" were flagged; 229 words became 110.
- **SQL:** the symptom list, the "consult docs/" pointer, and the 4 fault categories ("matching the four hidden faults exactly") were flagged; 140 words became 86.
- Both finished normally (`finish=stop`) in 15–35 seconds.

*Fairness watch:* the SQL rewrite leaves the business rules to be found in the environment's docs. That's allowed, but triage would flag it if it made failures the task's fault.

### Experiment: the static-site task with a trimmed instruction (17:13–17:20)
To test the "too much information" hypothesis on its own, the probe-1 static-site task (`petrify-static-site-broken-output`, 5 chained faults) was re-run 5 times with **only** `instruction.md` changed: the reviewer's rewrite (110 words, problem plus deliverable spec) instead of the original (229 words, one numbered symptom per fault). The copy lives in its log folder as `trimmed-instruction-task/`.

**Result: inconclusive.** 1 pass (26 steps), 1 fail (19 steps), and 3 runs cut off by the gateway (see below) at 22–25 steps, all three apparently about to pass. Compared with the original instruction (3 of 3 passed at 20–25 steps), the trimmed one did not visibly slow the agent down: all 5 agents had named the planted faults by about step 12–17.

**The one failure was the task's fault, not the model's.** The agent's homepage links were `../..` and `../../..`, which resolve to the site root correctly. The tests first confirm the link resolves to the root, then additionally assert `href.count('../') == 2` (or 3), so `../..` counts as 1. The instruction only required that links "resolve to the correct destination", never a trailing slash. Triage would have labelled this `task_fault` and rejected the task as unfair; the generator now prevents it:
- **Prompt rule (`QUALITY_RULES`):** tests check *meaning*, not spelling: resolve links and compare destinations, parse numbers/dates/JSON/paths, accept equivalent forms. An exact textual form may be required only if `instruction.md` states it. (Bad: `href.count('../') == 2`. Good: `resolve(page, href) == site_root`.)
- **Instruction review:** also checks the tests the other way round and reports `UNSTATED FORMAT: <test> requires <form>`.
- **Code gate (`difficulty.format_assertions`, in `files_gate`):** flags format-pinning assertions (`.count('../')`, `endswith('/')`, literal relative-path comparisons) whose form the instruction never mentions; the repair message asks for a meaning-based test or for the form to be stated. *Tested:* catches exactly the two failing assertions in the real test file; passes when the form is stated; ignores meaning-based tests; no false positives on the 6 older tasks.

### Gateway outage from 17:20
At **17:20:10 local** (00:20:10 UTC) the model gateway began answering every call with `401 "User not found"`. The last successful agent step was at 00:20:10 UTC and the first rejection one second later; three experiment runs died mid-step. Test calls at 17:22, 17:24, 17:31 and 17:43 all failed the same way. Spend to that point was small (eval cost $0.30 reported; generation about 1.4M glm-5.1 output tokens, roughly $3–7), so exhausted credits are unlikely; a 401 is an identity error (key revoked/rotated or account disabled), not a quota one. The `.env` values were re-entered by the user; the rejection persists. Nothing model-dependent can run until the key is valid again. Work continued on offline items (this fix, the commits).

## 2026-10-21 (evening): Hand-built hard reference task, `reference/petrify-stale-build/`
**Why:** every generated task so far was solved 5/5. Trajectory analysis showed the static-site task was a proofreading exercise: each fault was a visibly wrong line next to a comment stating the intended behaviour, and one `cat` showed the whole codebase. Before changing the prompts, we built one hard task by hand to learn what actually makes a task hard for terminus-2 + glm-5.3-flash.

**Ablation first (comments only, ~$0.15):** the same task with every confessing comment, docstring, README hint and decoy label removed, and the code unchanged, scored 2/5. All 3 failures were the **test's** fault: without the hint that links should be relative, agents wrote root-absolute links (`/css/…`), which the test resolved against the filesystem root. Under a fair test it would have been about 5/5. Conclusion: removing confessions alone doesn't make it hard; the visibly wrong lines are enough.

**The hard version** keeps the topic but makes each fault an interaction between correct-looking parts, with no comment stating intent:
- F1: the incremental manifest key omits templates and asset hashes. It only shows on the second build after an edit, and the old hashed file still exists, so links still "work".
- F2: the asset map is built before the theme adds its asset directory.
- F3: link normalisation expects a document URL; the builder passes a directory URL. Root clamping makes the code look consistent.
- F4: generic frontmatter coercion turns ISO dates into strings the date parser rejects.
- F5: redirect stubs overwrite a real page through a stale `redirects.yaml` entry.

Checks: tests resolve links rather than reading their spelling. 13/13 pass on the solved tree and 10 fail on the broken one; leaving out any single fix fails at least one test; oracle 1, nop 0; no confessing text.

**Result (stopped by the user once the verdict was clear): 3 passes of 3 finished, 2 stopped mid-run, so 4–5/5, still too easy.**
- The passes took **42–44 turns** (the easy version: 20–29). Each fault took about 3–22 turns to diagnose (easy version: all by turn 3–12).
- Behaviour changed as designed: agents read module by module (no single dump worked), and the leaders **built their own edit → rebuild → compare tests** for the incremental fault. Two runs read the link code and judged it correct before later catching F3 from output evidence.
- Of the 2 stopped runs: one had applied all fixes and was debugging its own validator (very likely a pass); one had just diagnosed F3 at turn 27 with no fixes yet.

**Lesson:** hiding faults doubles the work, but a careful agent with a 1-hour budget still finds every *findable* fault. Difficulty for this model has to come from places where careful, thorough work still leads to a *wrong* answer: an obvious fix that is incomplete (covering templates but not asset hashes in F1), requirements that can be met in several ways of which only one holds up under hidden scenarios, or work whose correctness the agent can't fully check itself. These, plus the earlier structural rules (no confessing comments, interaction faults, constructed conditions), are the inputs for the prompt changes.

## 2026-10-21 (night): Parts 3 and 4: batch metrics, ledger, resume, two copies at once
**Why:** the README asks for a funnel and yield on a 10+ batch (Part 3), and for a pipeline whose records explain every verdict, that resumes after a kill without re-paying, and that survives two copies at once (Part 4).

- **Batch ledger** (`generator/ledger.py`): `output/_batches/<batch>/` holds the topic list, one atomic state file per topic (pending → generating → generated → evaluating → done / gen_failed), per-topic `flock`s, and `audit.jsonl` (every stage change, with pid and reason). `pipeline.py --resume <batch>` continues a batch; `--report <batch>` rebuilds its report from the ledger alone.
- **Resume without re-paying:** every glm-5.1 reply is cached in the run's logs dir, keyed by model + prompts, so a resumed run replays finished calls for free; finished agent trials under the same run id are reused; a harbor job left running by `kill -9` is **adopted** (waited for, early stop still applied) rather than killed. Only a call or trial in flight at the kill is paid twice. Tested for real on the sample run: killed mid band-eval, resumed, the orphaned job adopted, nothing re-run.
- **Two copies at once:** per-topic locks split a batch between copies; output dirs are reserved atomically; run ids carry a random suffix; the history and report writes are locked. Found and fixed by the test: `write_task` deleted and recreated the task dir, and another copy could claim the name in the gap (1 collision in 6 runs before, 0 in 12 after).
- **Audit:** `VERDICT.md` in every task dir (stages, checks per round, a table of trials with failed tests and triage, the decision, the lesson, paths to the evidence); `band.json` keeps failed test names so the evidence survives if `jobs/` is deleted.
- **Report** (`output/_reports/<batch>.md`): funnel (spec → files → structural → correct → evaluated → learnable → kept → confirmed), yield, pass histogram, cost (generation priced at $1.40/$4.40 per M tokens and eval at $0.15/$0.50, gateway-reported cost when present), wall-clock time.
- **Tests:** an offline harness with fake model and harbor calls (`kill -9` mid-generation and mid-eval, resume, two copies, adoption, 12 repeated race runs, waves, slots, confirmation, genre tags); 61 checks pass. Record: `.claude/logs/2026-10-21-part3-4-test.md`.
- **Dashboard** (`generator/status.py`, `scripts/dashboard.sh`): processes, glm calls per stage, agent trials with their latest analysis, verdicts; optional `DASHBOARD_ONLY` focus for one experiment; run liveness by pid (a killed run no longer shows as live).
- **Gate fixes found by real runs:** a one-module tool's entry point (`python3 ledger.py …`), its output paths and the word "correct" (an event type) were flagged as hints; they no longer are.

## 2026-10-21/22: Why every generated task was too easy, and what changed
**Measured with terminus-2 + glm-5.3-flash at high effort, 5 runs each:**

| Task | What was varied | Result |
|---|---|---|
| log-summary example | as shipped | 5/5, 6–10 steps |
| fix-code-vulnerability with reference copies removed (no `.git`, no installed original, no network) | hand-edited | **3/5**, 26–113 steps; the one fair failure fixed `_hval` but not `_hkey` |
| identity (Unicode usernames) | with hints; then hints and checklist removed | 4/4; 5/5, 9–12 steps |
| inventory ledger A, B, C | trap stated in the instruction; trap removed; the correct replay path removed too | 4/4, 5/5, 4/4, ~10 steps each |
| incremental analytics; cache renderer | faults as interactions across runs, no reference, no hints | 4/4 (19–34 steps); 4/4 (9–16 steps) |
| statement-renderer (hand-built, 15 precisely stated rules) | specification task | 5/5, 8–22 steps |
| payment webhook | 3/5 at first | the failing assertion checked a receiver output the instruction never asked for: **unfair**, rejected; with that output stated, 4/4 |

**What the trajectories show.** The agent reads the code, forms hypotheses, writes its own end-to-end tests for every case it can think of, and iterates until they pass. Anything it can verify itself, it solves: it finds discrete hidden faults by reading, and it treats a numbered specification as a checklist and tests each item. Hiding more (instruction hints, reference copies, oracle commands) and adding more (faults, lines, layers, steps) changed the step count, never the verdict. The only fair failure came where the agent could **not** verify completeness and had to judge: it fixed the obvious site, re-tested the reported symptom, and talked itself out of the second fix.

**Decisions, in order, each taken after the evidence above:**
- **Quotas removed.** Fault count 5–7 → 2–4, no required layers, no decoy, no `depends_on` chain, no discovery-step grading (the critic's step estimates never predicted a result), no "2 different files" rule, no `solve.sh` or environment size floor. Each quota had produced filler (an unused wrapper typo, a wrong interpreter path, padding) rather than difficulty.
- **Fairness = derivable.** A test must follow from the stated goal plus domain knowledge and what the environment shows; it need not be written out, and the instruction must not list the traps (a checklist defuses them). Triage and the instruction reviewer use the same rule; a "model" triage verdict must quote the instruction sentence the run broke, otherwise it becomes "unknown" and the task goes to review instead of being kept (this is what caught the webhook task); 0/5 tasks are triaged too, so an unfair test is recorded rather than mistaken for difficulty.
- **No reference in the environment.** No correct copy of the tricky logic (the ledger's replay, which agents copied) and no runnable oracle (`verify`, a full rebuild to compare against, which agents fuzzed their fixes against). Checked in the spec and by a code scan of the written files.
- **Mutation check.** Each trap (or each rule) is run as an incomplete `solve.sh`; the tests must fail it before any agent spend. An equivalence check tells a real gap in the tests from a mutant that is behaviourally correct (the renderer lost its last repair round to one); one bonus repair round when only the mutation check fails.
- **Confirmation.** A task that lands 1–3/5 gets one more 5-run eval and is "confirmed" only if it lands again; a single 5-run sample favours lucky draws. The README verdict stays the first eval.
- **Early stop at 3 passes** with no failure yet (user's choice). 4 passes would be certain; 3 trades that certainty for time, since a true 3/5 task whose passes finish first is cut off and marked too easy.
- **Genre.** Fourteen variants inside the bug-hunt design space (hints on/off, reference copies on/off, oracle on/off, one-function vs interaction faults, 2–7 faults, 300–1,300 lines, five domains) all came back 4–5/5. When every lever in a design space fails, the design space is the problem, so the generator now builds two other shapes and keeps the old one only for comparison: **specification tasks** (build or transform to 12–20 independent, precisely stated rules over at least 4 themes, hidden inputs, no oracle: difficulty from breadth, nothing hidden) and **judgement tasks** (one stated property violated at several sites with distinct mechanisms and no way to confirm completeness: the shape of the one fair failure). A `[genre]` tag on a topic line picks the rules, gate, critic, reviewer and mutants; `scripts/topics-draft.txt` mixes 14 spec, 3 judgement and 3 hidden-fault topics on purpose, so the batch measures which shapes land. The hand-built statement-renderer (15 rules, 5/5) already shows that a precisely stated, fully testable spec is a checklist to this agent; the judgement runs are the open question.
- **Batch learning.** A post-mortem lesson per evaluated task (why it landed where it did) feeds the next spec and the critic through calibration, which only uses tasks built under the current design rules; `--waves` runs a batch in waves with a go/no-go gate between them; `BAND_SLOTS` caps concurrent band evals across copies; `scripts/run-batch.sh` starts N copies.

**Gateway facts (measured):** reasoning-effort settings are ignored for glm-5.1 (12-call probe, overlapping token counts at every level), but `reasoning: {enabled: false}` and a reasoning token budget are honoured; `max_tokens` caps cut replies off; `:nitro` gains nothing. Spec calls take 7–18 min, about 90% of it hidden reasoning; the critic 6–16 min.

**Part 3 status:** `part3-batch-1` (hidden-fault genre, stopped after 3 of 8 topics once the pattern was clear): 1 too easy, 1 rejected as unfair after re-triage, 1 failed generation on its last repair round (an untested trap); $3.04. Spend on all batch reports so far $8.01, plus about $3 of hand experiments. Three runs under the mixed-genre rules (two judgement, one spec) are in progress.

**Open:** the 20-topic batch (`bash scripts/run-batch.sh scripts/topics-draft.txt <batch> 3 6,14`) waits on those three results; a "preserve existing behaviour" rule with regression tests, so rewriting a starter from the spec is the wrong move; a report column comparing the critic's flags with the band result, since its verdicts have never been checked against outcomes; `.bak` cleanup before packaging.

## 2026-10-22: Six task shapes measured; one recipe for every topic
**Measured with terminus-2 + glm-5.3-flash at high effort, 5 runs each (early stops on):**

| Task | Shape | Result |
|---|---|---|
| HTTP header injection (regenerated under the required-handling rule) | judgement | 3/3, too easy |
| billing rounding (generated) | judgement | 3/3, too easy |
| billing, hand-edited: float-derived rates and a global `Decimal` precision change added | judgement | 1/3 but **unfair** (the instruction said every rate is exact, a docstring said exchange rates are cut to 6 figures; two runs followed the instruction); with the exception named: 3/3 |
| ledger report, hand-built: six chained build, ABI, lock, tz-data and logic obstacles | long road | 3/3 in 8–9 steps |
| Markdown table formatter (18 stated rules) | spec | first eval 0/5 from three **unfair** tests (a column with no data rows was numeric by rule 7's literal wording; `--check`'s exit code); fixed: 4–5/5, stopped early |
| packing slip | spec | 3/3, too easy |
| mainframe EBCDIC extract, hand-built: COMP-3, `SIGN IS LEADING`, `P` scaling, alternate sign nibbles | domain | 5/5 |

**What the trajectories show.**
- **The model fixes by reading.** On the ledger task every run read every file first and fixed all six obstacles in one batch of edits; the chain only exists for someone who fixes by trial and error.
- **It knows more niche detail than expected, and it builds its own test data.** Every EBCDIC run wrote its own encoder to make synthetic records and checked its converter against them.
- **Most "learnable" results were task faults.** Three of the four in-band results this week (webhook, HTTP, billing) and the Markdown 0/5 came from a contradiction or an unstated choice. The tell: every failing run fails the same assertion.
- **Generated tasks are small.** Expert estimates of 20–45 minutes and 300–500 line projects; every one was solved in 8–30 steps.

**Decisions, in order:**
- **Early stops, one switch each.** A band eval also stops as learnable at one pass plus two failures (certain). `EARLY_STOP_FIRST_PASSES`, `EARLY_STOP_TOO_EASY` and `EARLY_STOP_LEARNABLE` turn each stop off on its own, e.g. to give triage every failure.
- **Judgement fairness rules.** Every exception to a "must hold everywhere" property is named in the instruction, never left to a docstring; a correct helper that the violating sites merely bypass is an answer key ("use `round_money` everywhere" fixed every billing site). Triage: a run that followed one instruction sentence and broke another is the task's fault (triage had called both billing failures the model's).
- **Leaked-answer check narrowed.** It flagged rule constants (`40.0` matched inside `0.0`) and required output labels; payroll lost four repair rounds making its instruction vaguer. Now only computed-looking values, matched as whole tokens.
- **Spec rules live in a document the instruction names** instead of a numbered checklist; the gates exempt that document and coverage, review and triage read it.
- **Long-road genre** (chained real failure modes to an exact end state), then the rule its first result taught: at most one obstacle may be readable in the source.
- **Domain genre** with expected values from a pinned library installed only for the verifier, so a detail the generator misremembers cannot make the solution and the tests wrong together.
- **Knowledge probe and dial.** Before any files are written, glm-5.3-flash answers each knowledge point five times; the product of the rates predicts the pass rate and steers the design to 20–60%. A 14-question run: EBCDIC 80–100%, CRC and SAM 100%, time scales 80–100%, **ISDA day counts 0–20%** (Bond Basis treated as US 30/360, 30E/360 ISDA confused with 30E/360, Actual/Actual ISDA off by a fixed amount). Calls are cheap; 70 took about 5 minutes when the gateway was slow, seconds when it was not.
- **Generated-input tests: a fairness tool, not a difficulty lever.** 1,500 seeded tables compared with the reference found three ambiguities 55 fixed tests had missed (truncation and column width, merging an empty extra cell, rule 1's own example); after fixing them two of the four agent tools matched the reference on every table. `FUZZ_TESTS` is off by default.
- **Executable reference, then one recipe for every topic.** The specification becomes a stripped C binary the agent can run but not read; it must probe for 8–15 decision points (rounding steps, tie-breaks, boundaries, byte layout) and build an artifact that matches on hidden inputs of the sample's kinds. Tests compile a pristine copy of the reference and compare about 500 generated inputs; the oracle check proves the task solvable; one mutant per decision point. Every topic now uses this recipe (`TOPIC_TAGS=1` brings back the others), and the topic list is 16 black-box topics.

**Why the executable reference.** Every shape above failed the same way: whatever the agent can read (code, rules, faults) or already knows (standards), it verifies and gets right. A reference it can only run keeps the specification observable, so the task stays fair, while making coverage the work: runs differ by how thoroughly they probe and when they decide they are done. A hand-built test (a mawk report script to port byte for byte, quirks such as `substr(s, 0, 4)`, byte-wise UTF-8, 32-bit integer printing) produced the first early trajectories that disagreed instead of converging; one run concluded the wrong comparison rule.

**Operational facts.**
- Gateway failures rose from about 2% of calls (00:00–04:00) to about 24% (04:00–05:30): dropped connections and empty replies after long reasoning. Not call length (successful calls ran up to 20 minutes), not our concurrency, not prompt changes; recovered by 05:32.
- Stopping a background shell does not stop the harbor job it started: its agent containers keep running. Stop the pipeline (its handler cleans up) or run `checks.cleanup_job` on the job.

**Open:** the awk parity result and the first three generated executable-reference tasks (tax calculator, shift scheduler, bond day counts); the Part 3 funnel report for today's runs; `.bak` cleanup before packaging.

### Later on 2026-10-22: the parity test, gate conflicts, early stop
- **awk parity port, hand-built (no early stop): 5/5, too easy.** Port a legacy mawk report script to Python, byte-identical on 200 hidden files; the reference port matched mawk on 2,201 of 2,201 files, so the task was solvable. Runs took 38–85 steps (against 8–15 on earlier tasks) and two held wrong beliefs mid-way, but every run kept comparing its output with `awk` until they matched. A runnable reference shows the agent its own mistakes; for the band, the hidden inputs need behaviour the sample's kinds do not lead it to probe.
- **The first generated executable-reference tasks failed generation on our own gates.** The location gate flagged the instruction for naming the reference binary, which is the interface, and the oracle gate flagged `reference.c`, which the Dockerfile compiles in a build stage and never ships. The tax calculator and bond day-count builds each lost four repair rounds (about 1.5 hours). The gates now allow both, but only when the final stage does not copy the source; otherwise they say how to fix the Dockerfile.
- **Three-pass early stop off by default.** It cut the parity eval off before the last runs finished; the stops that cannot change a verdict (4 passes; 1 pass and 2 failures) stay on.
- **Lesson for running evals:** an eval script started on its own keeps its harbor job running if the script is killed; that was used here to let the parity eval finish all five runs without the old early stop.

## 2026-10-22 (late morning): one recipe, a leaner pipeline, seed cards
**Why:** every task shape built or generated today came out too easy, and the common cause was what the agent could check (read, already know, or run). The pipeline also spent hours on our own gates fighting the designs.

- **One recipe for every topic.** The six per-genre recipes were folded into one design rule: difficulty comes from an evaluation the agent cannot reproduce in full (held-out data, load generators, hidden edge cases, varied draws), and ground truth is always computed by code the tests run, never by the generator's reasoning. Fairness rules from every recipe were kept; topic tags, per-genre gates and the knowledge probe were removed (prompts.py went from about 1,300 to 610 lines).
- **Difficulty knobs:** 2-4 per design, each with its fairness condition (drift, stated precedence, stale local tests, preservation, hidden edges, conventions, seeded service faults, resource ceilings, audited steps, authoritative sources, varied draws). A design with no knob is too easy; a knob without its condition is unfair.
- **Topic list v3:** 15 topics in shapes that land at 1-3/5 for glm-5.3-flash in public per-task results, scored for diversity (8 shapes; C, Fortran 77, Go and services alongside Python), every subject new.
- **Less duplicate work.** The files gate now blocks only on reliable checks (missing spec document, reference source reaching the image, oracles, answer copies); its pattern scans (pasted values, file names, pinned formats, pointers, rule coverage) became hints for the instruction review. As blockers they had caused about a dozen false-alarm repair rounds today. Triage per failed run and the post-mortem were merged into one band-review call per task.
- **Retry limits** are each adjustable by environment variable and can be switched off together (`RETRY_LIMITS=0`), in which case a safety cap (`RETRY_SAFETY_CAP`, default 10) still bounds cost.
- **Design gate fix:** two checks count as duplicates only if they repeat both the requirement and the hidden input; hidden-evaluation tasks legitimately quote one sentence for several checks.
- **Seed cards.** A topic line `@seeds/<name>.yaml` feeds a binding card to the design: shape, what the agent cannot verify, the difficulty dial, a quirk matrix (dimensions x levels and the mix), public common-path tests (about 30% of coverage, the one other allowed visible tests, so the agent's verify loop works), an anti-cheese gate, how ground truth is computed, seed checks, knobs, what must be kept, environment limits, what is out of bounds, and pre-checks. The card rides in the design to every later stage; the gate rejects a design that drops its dial, matrix, public tests or gate; the review and oracle scan allow the public tests; the tool and public tests must run in under 60 s. Cards exist for all 15 topics. *Alternative considered:* one-line topics, which left the decisions that set difficulty (what the agent cannot verify, the dial) to the generator, and it chose checkable designs again and again.
- **Operations:** an eval script killed on its own leaves its harbor job running, which was used to let the parity eval finish all five runs. The dashboard can show experiments outside the main folders through `jobs/.dashboard-extra.json`.

**Stretch goal A, on branch `stretch-goals` (a separate worktree, merged later):** every test's result is kept per run and shown as a per-test table, with a flag naming tests that every failing run failed (it reproduces the three unfair Markdown tests found by hand). A per-task adjustment step (off by default) makes at most two fair edits (harden, ease, or fix only the triaged fault), re-checks with validator, oracle, nop and mutants, restores the task if a check fails, and re-evaluates. Its first real proposal invented mawk behaviour and wrote an expected output for it; edits to data files under tests/ are now refused, and data files are listed rather than pasted (prompt from about 119k to 3k tokens).

**Open:** the five seed-card topics (`seeds5-102558`) and the stretch-test re-run are in progress.

## 2026-10-22 (midday): seed cards v2, the agent never runs the answer key, one merged branch
**Why:** the seed-card batch designed faster (specs passed the gate on the first try instead of after one or two rejections, and calls took 5-13 minutes instead of 15-21), but a check of what the agent could still run showed the same weakness that made the awk port 5/5: a reference it can run is an answer key.

- **Seed cards v2 (branch `seed-cards-v2`).** The design rule now separates PRACTICE from GRADED instances (the agent gets one set; the tests generate different instances from sibling seeds and check the generator is deterministic), requires an exact observable CONTRACT (entry point, outputs, exit codes, precedence, every line stated in instruction.md), at least one INVISIBLE TRAP (a plausible wrong solution with no runtime signal, stated in the instruction), and anti-cheese enforced at run time, not only by scanning source. New spec fields carry these (`graded_instances`, `contract`, `invisible_traps`, `instance_plan`, and `caught_by_tests` per check); the seed gate requires them and the instruction review checks that every contract line is stated. A mutant now counts as caught only by the tests its check names (a mutant caught elsewhere counts as survived), and the oracle must finish within a time budget (`ORACLE_MAX_SEC`, default 180 s; `VERIFY_MAX_SEC`, 420 s). Three cards (route speed-up, GBM trace, variable stars) were upgraded to the new fields and run as a separate batch.
- **Reference access (decision).** The agent never runs code whose output answers the graded question. A reference program that defines the behaviour (a legacy interpreter, binary or library) runs only in tests/ and the verifier's packages; the agent gets the named version, its documentation or source, and a frozen practice set of input/output pairs in which every graded quirk appears at least once. New spec fields `reference_access` (`none`, `frozen_examples`, or `runnable: <reason>`) and `quirk_evidence` (the file that shows each quirk); the gate rejects a missing or bare value, a quirk without evidence, and a reference binary in the agent's image unless it is runnable. `runnable` is kept for tasks where matching is not the hard part (the route speed-up: the hard part is the 10x target). All 15 cards carry the new fields; the Tcl/Tk port no longer ships `tclsh` to the agent. *Evidence:* the awk port with mawk installed passed 4/4, and every run of its hardened version again started by fuzzing its port against mawk on hex numbers, signed decimals and non-ASCII bytes, exactly the cases the harder hidden test was meant to catch. *Alternative considered:* removing the reference with nothing in its place, which is unfair for implementation-specific behaviour (mawk's 32-bit `%d`), since only running it shows that. *Consequence:* the executable-reference approach (a stripped binary the agent can run but not read) is retired: it hid the source but still allowed unlimited comparisons.
- **Stretch A fixes (branch `stretch-goals`).** The adjustment step rewrote every task file after an edit, reading data files as text: CRLF became LF in 153 of the awk task's 200 hidden inputs and binary files would have been deleted, so the oracle failed and a correct edit was rejected. It now writes only the changed files. The re-checked edit (a seeded hidden fuzz test whose expected values come from mawk itself) passed oracle 1 / nop 0 and is being re-evaluated.
- **One branch.** `merged` combines main, `stretch-goals` and `seed-cards-v2` (no conflicts; offline suite 65/65) plus the reference-access rule. The five seed-card topics were stopped in design on main and restarted on `merged` (`merged-105846`).
- **Operations.** Worktrees share the main `.venv` through a symlink (git-excluded locally): without it, harbor was missing at the first oracle check. Harbor resumes a job whose name already exists, so a re-run with a reused run ID silently returns the old result; pipeline run IDs are unique, test drivers now add a timestamp. The dashboard's eval section reads the extra worktree job folders; "missing on 6" in a gate message is the check's index, not a count.

**Open:** the merged batch (five topics), the v2 batch (three topics) and the hardened awk re-evaluation are running.
