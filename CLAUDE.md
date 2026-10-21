# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context
This repo contains a pipeline that generates tasks to be evaluated by Terminal-Bench 2. A generated task needs to be of the right difficulty i.e. it should be hard but solvable and fair. Hard in the sense that it has a long horizon (multiple steps, where errors compound), an agent needs to discover/explore the environment, it has real failure modes (cryptic errors, dependency errors, long running processes), failure cascades/loops, and ambiguity a real expert could resolve. The task must also be learnable.

The pipeline will generate tasks with `glm-5.1` and benchmark difficulty only against `glm-5.3-flash`. The evaluator reasoning effort will be a constant set at "high". Use no other models for either generation or evaluation.

## Communication Style
* Write in clear, simple, conversational English. No buzzwords, filler, or corporate jargon.
* Explain concepts as if speaking to an intelligent beginner.
* Use practical examples. When possible, show how state changes across an example.
* Use short paragraphs, headings, and lists.
* Stay within requested word counts and formats.

## Definitions
* Terminal-Bench 2: A benchmark for testing how well agents can do real difficult work in a computer terminal.
* Learnable Task: Tasks that pass sometimes but not all the time e.g. when run 5 times with `terminus-2` using `glm-5.3-flash` at `reasoning_effort=high`, exactly 1 to 3 out of 5 runs pass all tests. 

## Environment
* macOS, zsh. Helper scripts in `scripts/` are bash.
* Python is the repo's uv venv at `.venv` (Python 3.12, gitignored). Never use system `python3` (3.9.6, too old); there is no bare `python` on the host.
* `scripts/*.sh` use `.venv/bin/python` automatically. For anything else, call `.venv/bin/python` / `.venv/bin/harbor` directly; shell activation doesn't persist between Claude's commands.
* Docker Desktop must be running for `harbor run`. Claude's shell doesn't load `~/.zprofile`, so `docker` isn't on its PATH; prefix harbor commands with `PATH="$HOME/.docker/bin:$PATH"`.
* Secrets live in the repo-root `.env` (gitignored, `chmod 600`; template in `.env.example`). `generator/config.py` loads it automatically; pass `--env-file .env` to every `harbor run` that calls a model. Exported variables override the file.
* The model endpoint (`OPENROUTER_API_BASE`) must be set in `.env`; there is no default. Don't hard-code it or take it from the README, whose gateway rejects the provided key.
* Quote paths that contain spaces. Write text files as UTF-8.
* Avoid heavy folders in the repo (e.g. `node_modules`). `.venv` is the one exception and must stay gitignored.
* Always back up a file before editing or rewriting it, as `<file>.bak`, `.bak2`, etc. `.gitignore` excludes `*.bak*`, so backups never get committed.
* Commit history is a graded deliverable (README). Commit in small, descriptive steps, and only when asked.

## How to Work
* For complex tasks:
    - Ask clarifying questions until the goal, inputs, output format, and constraints are clear. Ask the most important first. Skip questions the files already answer.
    - Design and plan in plan mode. Present the plan and wait for approval before changing files.
    - Execute step by step, then review and improve weak areas before delivering.
* When several approaches exist, explain the tradeoffs and give a recommendation.
* Before running a command that changes files, installs software, or uses the network, say in one line what it does.

## Permission Tiers
* **Do freely:** read files, search, run read-only commands, create drafts and temporary files.
* **Ask first:** overwrite or delete files, move files between folders, install packages, change settings, create new top-level folders, anything outside this folder.
* **Never:** read, print, or copy `.env`; put secrets, API keys, or personal data in any other file; send project data to external services without approval; edit this CLAUDE.md unless asked.

## Scope Control
* Do only what was asked. List extra ideas under "Next step" in the Final Report instead of doing them.
* Prefer editing an existing file over creating a new one.
* If the task grows beyond the approved plan, stop and re-confirm.

## Assumptions and When Stuck
* If missing information would change the result, stop and ask.
* If it would not, pick the simplest option, label it `Assumption:` in the Final Report, and continue.
* After 2 failed attempts with the same approach, stop and report what was tried, the error, and 2 options for next steps.
* Never hide or work around a failing test without saying so.

## File Naming and Versioning
* Use lowercase, hyphens instead of spaces, descriptive names, and no special characters (e.g. `ai-agent-research.md`), unless instructed otherwise.
* Confirm the file name before creating a deliverable. Temporary and draft files do not need confirmation.
* Never overwrite a delivered or final file. Save a new version instead (e.g. `report-v2.md`).

## Folder Structure
* examples: reference tasks in the standard Harbor format. These are examples which means they may not be in the target difficulty.
* generator: core Python scripts behind the pipeline.
    - generate.py: task generator. Builds a Harbor task from a topic string. Currently a stub; most work happens here.
    - config.py: config constants and env-var overrides.
    - requirements.txt: Python deps for the generator. Install in any new Python environment.
* harbor: the Harbor framework source. This is the harness that runs agents against tasks. Read it to understand how it works: the `task.toml` schema, the agents, the verifier. The framework itself is installed in `.venv` (see Commands).
* output: folder inside of which output (generated tasks) will be created.
* scripts: helper scripts for generation and validation.
* validator:
    - validate.py: structural validator (layout + task.toml schema).
    - requirements.txt: notes it needs Python 3.11+ (tomllib); the native cross-check runs because harbor is installed in `.venv`.

## Commands
```bash
# one-time setup (uv is installed via Homebrew)
uv python install 3.12
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r generator/requirements.txt harbor
cp .env.example .env && chmod 600 .env       # then fill in the key yourself

# toolchain sanity check on a known-good example (oracle verified at reward 1.0)
bash scripts/validate.sh examples/fix-git
PATH="$HOME/.docker/bin:$PATH" .venv/bin/harbor run -p examples/fix-git -a oracle

bash scripts/generate.sh "<topic>"           # -> output/<slug>/
bash scripts/validate.sh output/<task>       # exit 0 = pass
PATH="$HOME/.docker/bin:$PATH" .venv/bin/harbor run -p output/<task> -a oracle   # expect reward 1
PATH="$HOME/.docker/bin:$PATH" .venv/bin/harbor run -p output/<task> -a nop      # expect reward 0
PATH="$HOME/.docker/bin:$PATH" .venv/bin/harbor run -p output/<task> -a terminus-2 --env-file .env \
  -m openrouter/z-ai/glm-5.3-flash \
  --ak reasoning_effort=high --n-attempts 5  # learnable = 1-3/5
# cheap smoke test before the paid 5-run eval: same command with --n-attempts 1 (the default)
```
* Commands are written for Claude's shell (no venv activation, no `~/.zprofile`). In your own terminal, `source .venv/bin/activate` and plain `harbor run ...` work too.
* There are no unit tests or linters. The only checks are validate.sh plus the oracle/nop runs.
* `harbor run` writes results to `jobs/` (gitignored); read rewards and agent/verifier logs there to explain a failure.

## Architecture
* Pipeline stages: generate (glm-5.1) → structural validate → oracle/nop correctness check → 5-run band eval → keep only tasks that pass 1–3 of 5. `generate_task()` in generator/generate.py is a stub and returns None today. It still runs `os.makedirs(output_dir)` first, so each `generate.sh` run leaves an empty folder in `output/`.
* `generator/config.py` holds all knobs, each overridable by env var: `GENERATOR_MODEL`, `EVAL_AGENT`, `EVAL_MODEL`, `EVAL_REASONING_EFFORT`, `N_RUNS`, `BAND_LOW`/`BAND_HIGH`, `CANARY_GUID`. Read from there; don't hard-code.
* Reward contract: `tests/test.sh` writes `1` or `0` to `/logs/verifier/reward.txt` (see harbor/src/harbor/verifier/verifier.py).
* Canary: stamp `CANARY_LINE` into solve.sh, Dockerfile and test_outputs.py. Leave it out of instruction.md; Harbor strips it there.
* Generated tasks build from `environment/Dockerfile`. The examples use a pre-built `docker_image`; don't copy that.
* Start new tasks from the scaffold at `harbor/src/harbor/cli/template-task/`. It's only a starting point: the generator should overwrite values that break the validator (agent `timeout_sec` 900 → ≥ 3600, add `[task].name` and `[metadata].difficulty`) and use `pytest-tests/` as `tests/`. Don't edit the scaffold in `harbor/` itself.
* Validator errors (fail, exit 1), from validator/validate.py:
    - `task.toml` or `instruction.md` missing or `instruction.md` empty, or `environment/`, `solution/`, `tests/` missing.
    - `[agent].timeout_sec` missing or < 3600; `[verifier].timeout_sec` or `[environment].build_timeout_sec` not positive; `[metadata].difficulty` not in easy/medium/hard/unknown; `[task].name` not in `org/name` format.
    - No `environment/Dockerfile` (or compose file / `docker_image`), or a Dockerfile without `FROM`.
    - No `solution/solve.sh`, no `tests/test.sh`, or `test.sh` never mentions `reward.txt` / `reward.json`.
    - Harbor's own `TaskConfig` / `Task.is_valid_dir()` check rejects the task (runs only if `harbor` is importable).
* Validator warnings only (still exit 0): no canary in solve.sh / Dockerfile / tests, no `.py` files in `tests/`, harbor not importable. Passing validation does not prove the canary is stamped; check it yourself.
* `generate.sh` and `validate.sh` `cd` into `generator/` and `validator/` before running, so modules there import each other flat (`from config import ...`), not as a package.

## Deliverable Constraints (from README.md)
* Tasks must be novel. Don't reuse or adapt public tasks, including examples/.
* A failing run must be the model's fault, not the task's. Timeouts don't count. Know why every shipped task fails.
* Guard against reward hacking (tests that can be gamed, answers leaked in the environment).
* Keep the batch diverse; near-duplicate tasks are worth less for training.
* Keep cost reasonable: $200+ for one task is too much. Ask for a credit top-up rather than cutting corners.
* Part 3 metrics: run a batch of 10+ tasks and report counts at each stage (structural pass, oracle/nop correct, 1–3/5 learnable), yield rate, and total cost and time.
* Priority: Parts 1–3 (a valid, correct, learnable batch) beat Part 4 (robustness). Stretch goals (difficulty tuning, then human-likeness vs examples/) only after Parts 1–4 are done.
* Robustness (Part 4): keep an audit record of every step and verdict; resume after being killed without re-paying for finished runs; stay safe when two copies run at once.
* Record what was done, why, and the design tradeoffs in CHANGELOG.md (graded deliverable).

## Workflow and Agent Design Standard
Every workflow or agent definition must state:
* **Purpose:** one sentence.
* **Inputs:** what they are and where they come from.
* **Outputs:** what they are and where they go.
* **Tools:** which tools it may use.
* **Steps:** numbered. If there are more than about 10, split the workflow.
* **Stop condition:** how it knows it is done.
* **Failure handling:** what to do when a step fails.
* **Worked example:** one sample input and the expected output.

## Verify (Testing Protocol)
Every output must be tested before delivery, using the method for its type:

| Output type | How to test | Proof |
|---|---|---|
| Code or scripts | Run with a sample input; run existing tests | Command and key output in the Final Report |
| Workflows or agent definitions | Dry run on one sample input | Walkthrough of the result in the Final Report |
| Documents | Check against the requirements and Success Criteria | Pass/fail list in the Final Report |

* For complex tasks, save a test record to `.claude/logs/yyyy-mm-dd-<task-name>-test.md` describing how testing was done and the results.

Main check for a generated task: validate.sh, then oracle (reward 1), nop (reward 0), then the 5-run band eval. See Commands.

## Final Report Format
End every task with:
1. **Done:** what changed, with file paths.
2. **Tested:** how it was tested, and the result.
3. **Open issues:** anything skipped, assumed, or uncertain.
4. **Next step:** one suggested action, if any.

## Progress Tracking
* For tasks that span more than one session, keep `<task-name>-progress.md` with: done, in progress, next step, open questions.
* Update it at the end of each work session.

## Success Criteria
A successful output is:
* Clear and easy to understand
* Accurate
* Concise
* Actionable and immediately useful
