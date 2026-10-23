# Running the pipeline and the dashboard

Everything below runs from the repo root on macOS. The project's own `README.md` is the brief; `CHANGELOG.md` is the decision record; `glossary.md` defines the terms.

## One-time setup

```bash
uv python install 3.12
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r generator/requirements.txt harbor
cp .env.example .env && chmod 600 .env      # then put the API key and the endpoint in .env
```

- `.env` holds `OPENROUTER_API_KEY` and `OPENROUTER_API_BASE`. Nothing else reads or copies it; every `harbor run` that calls a model gets `--env-file .env`.
- Docker Desktop must be running. From a shell that has not loaded `~/.zprofile`, prefix harbor commands with `PATH="$HOME/.docker/bin:$PATH"`. In your own terminal, `source .venv/bin/activate` and plain `harbor run ...` work.
- Models: glm-5.1 generates, glm-5.3-flash is evaluated, at reasoning effort high. Both are fixed in `generator/config.py`.

Sanity check on a known-good task:

```bash
bash scripts/validate.sh examples/fix-git
harbor run -p examples/fix-git -a oracle          # expect reward 1
```

## Topics and seed cards

A topic line is either free text or a reference to a seed card:

```
@seeds/ids-rules.yaml
@seeds/microgrid-forecast.yaml
```

Cards live in `scripts/seeds/`; `scripts/topics.txt` lists all fifteen. A card binds the design: shape, what the agent cannot verify, the dial, the quirk matrix and its evidence, public tests, anti-cheese, ground truth, checks, knobs, must-keep behaviour, environment limits, out-of-bounds choices, answer source, reference access, self-check gap. To add a topic, copy a card, fill every field, and add its `@seeds/` line to a topics file.

## Generating and evaluating

One task from one topic, with no evaluation (writes `output/<task>/`, logs under `output/_logs/`):

```bash
bash scripts/generate.sh "@seeds/ids-rules.yaml"
bash scripts/validate.sh output/<task>                 # structure and task.toml
harbor run -p output/<task> -a oracle                   # expect reward 1
harbor run -p output/<task> -a nop                      # expect reward 0
```

The full pipeline on a topics file (design, gates, critic, files, review, validator, oracle, nop, mutants, 5-run band eval, review, verdict):

```bash
bash scripts/pipeline.sh --topics scripts/topics.txt --batch-id my-batch
```

Several copies share one batch through the ledger's per-topic locks; each copy takes the next free topic:

```bash
bash scripts/run-batch.sh scripts/topics.txt my-batch 3          # 3 copies
bash scripts/run-batch.sh scripts/topics.txt my-batch 3 3,7      # in waves: 3 topics, then 7 if the first wave passed its gate
```

Five random seed cards, five copies in parallel, with the dashboard started for you (the quickest full run):

```bash
bash scripts/run-five.sh                 # picks 5 cards at random, opens jobs/dashboard.html, waits, writes the report
DRY_RUN=1 bash scripts/run-five.sh       # shows the picks and the commands without starting anything
```

Other modes:

```bash
bash scripts/pipeline.sh --resume my-batch            # continue after a kill; finished model calls replay from cache, free
bash scripts/pipeline.sh --report my-batch            # rebuild the batch report from the ledger alone
bash scripts/pipeline.sh --eval-only output/<task>    # band-evaluate an existing task (hand-built or edited)
bash scripts/pipeline.sh --smoke output/<task>        # one agent run to check the eval config, no verdict
bash scripts/pipeline.sh --topics f.txt --limit 2     # first two topics only
bash scripts/pipeline.sh --topics f.txt --control     # A/B control arm (no difficulty rule, results kept out of calibration)
```

A 5-run eval by hand, outside the pipeline (results land in `jobs/` and show on the dashboard):

```bash
harbor run -p output/<task> -o jobs --job-name band-<task>-$(date +%H%M) -a terminus-2 --env-file .env \
  -m openrouter/z-ai/glm-5.3-flash --ak reasoning_effort=high --n-attempts 5 -q -y
```

## Where things go

| Path | Contents |
|---|---|
| `output/<task>/` | tasks that passed every check; a kept task also has `band.json` and `VERDICT.md` |
| `output/_rejected/<task>/` | evaluated tasks outside the band or unfair, with their `VERDICT.md` |
| `output/_logs/<topic>-<time>/` | every run: `events.jsonl` (calls, tokens, gates, checks), raw model replies, `spec.json`, `critic.json`, the reply cache, `last-attempt/` for a failed build |
| `output/_batches/<batch>/` | the ledger: topic list, one state file per topic, locks, `audit.jsonl` |
| `output/_reports/<batch>.md` | funnel (designed, built, correct, evaluated, learnable, kept, confirmed), yield, pass histogram, cost, time |
| `output/_logs/calibration.jsonl` | one line per evaluated task, fed back into the next designs |
| `jobs/` | harbor job folders: one trial per run with the agent trajectory and the verifier output (gitignored) |

## Settings (environment variables, read when a process starts)

| Variable | Default | Effect |
|---|---|---|
| `MAX_REPAIR_ROUNDS` | 3 | repair rounds after a failed check (`BONUS_REPAIR_ROUND=1` adds one when only mutants fail) |
| `MAX_SPEC_ATTEMPTS` | 2 | spec calls when the design gate rejects |
| `LLM_MAX_RETRIES` | 2 | re-sends of a model call after an error or an unusable reply |
| `MAX_INVALID_RERUNS` | 3 | extra eval runs to replace timeouts and infrastructure errors |
| `RETRY_LIMITS=0` | on | lifts all the above to `RETRY_SAFETY_CAP` (10) |
| `MUTANT_TOLERANCE` | 1 | surviving mutants recorded as test weaknesses instead of repaired |
| `MUTATION_CHECK` | 1 | 0 skips the mutant stage |
| `SPEC_CRITIC`, `INSTRUCTION_REVIEW` | 1 | 0 skips the critic / the instruction review |
| `NEED_TO_KNOW` | 1 | 0 lets the single files call write the instruction and documents again |
| `GEN_REASONING_BUDGET_<STAGE>` | 24k spec/critic, 16k project/files/repair/mutants | hidden-reasoning budget sent to the gateway (advisory) |
| `BAND_SLOTS` | 2 | band evals running at once across a batch's copies |
| `EARLY_STOP_TOO_EASY`, `EARLY_STOP_LEARNABLE`, `EARLY_STOP_FIRST_PASSES` | 1, 1, 0 | each early stop on its own switch |
| `N_RUNS`, `BAND_LOW`, `BAND_HIGH` | 5, 1, 3 | runs per eval and the learnable band |
| `FUZZ_TESTS` | 0 | generated-input tests against a hidden reference (a fairness tool) |
| `ADJUST_ROUNDS` | 0 | stretch goal A: fair edits to a task that landed outside the band |

Example: `MAX_REPAIR_ROUNDS=5 BAND_SLOTS=3 bash scripts/run-batch.sh scripts/topics.txt b2 4`.

## The dashboard

```bash
bash scripts/dashboard.sh 15        # re-renders jobs/dashboard.html every 15 s; Ctrl-C to stop
open jobs/dashboard.html            # the page reloads itself every 10 s
```

It is read-only: it looks at processes, Docker, and the logs the pipeline already writes. Sections:

- **Now:** pipeline processes, how long they have run, their topic.
- **GLM activity:** every run's stage, attempt and retries, what glm-5.1 is doing right now and for how long, and the current design's name, check count and knobs.
- **glm-5.3-flash:** each running agent trial with its turn count and phase, its latest analysis (scrollable) and latest commands.
- **Docker containers**, **Runs (last 3 h)** with their current stage and age.
- **Agent evals:** every band eval of the last 3 hours, run by run, with the verdict (learnable, too easy, too hard, invalid, inconclusive; the certain verdict while runs are still going).
- **Difficulty knobs**, **Recent verdicts** (pipeline verdicts and finished harbor jobs of the last 24 h, newest first), and today's eval cost and generation tokens.

Options:

- `DASHBOARD_ONLY=<text> bash scripts/dashboard.sh` shows only processes, runs and jobs whose name or path contains the text.
- `jobs/.dashboard-extra.json` adds folders outside the repo (for example a worktree's `output/_logs/*` and `jobs`): `{"logs": ["/path/output/_logs/*"], "jobs": ["/path/jobs"]}`. Wildcards are allowed; it is re-read on every render.

## Reading a result

- `VERDICT.md` in the task folder (or in its log folder when the build failed): the gate and critic results, each check round, the per-run table with failed tests and triage (model's fault or task's fault, with the sentence the run broke), the per-test table, the decision and the lesson.
- A failing run must be the model's fault for a task to be kept; a task is rejected as unfair if any failure is the task's. Timeouts are invalid and re-run, never counted as failures. A learnable task gets a confirmation eval before it is kept.
- The batch report under `output/_reports/` gives the funnel and yield; `--report` rebuilds it at any time.

## Stopping and cleaning up

- Stop a pipeline with Ctrl-C or `kill -TERM <pid>`: its handler stops its harbor jobs and removes their containers; the ledger lets `--resume` continue it.
- A `harbor run` started by hand keeps running if its shell is killed; stop it with `kill -TERM` on the harbor process, then `docker ps` to confirm its containers are gone. Harbor reuses a job name that already exists, so give a re-run a new name.
- The offline robustness suite (65 checks: kills, resume, two copies, races, waves) lives outside the repo in the session scratchpad; see the CHANGELOG entry "Parts 3 and 4" for what it covers.
