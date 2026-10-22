"""
Prompts for the authoring model. Three calls:

  1. SPEC   – design the task (JSON, no code)
  2. FILES  – write the task files from the spec (file blocks)
  3. REPAIR – fix the files after a failed check (file blocks, changed files only)

task.toml, tests/test.sh and the canary are written by Python, so the model
never sees or edits them.
"""

import json

from config import CRITIC_FOUND_WITHIN, DISCOVERY, MAX_FAULTS, MIN_ENV_LINES, MIN_FAULT_LAYERS, MIN_FAULTS

# Paths the model is allowed to write. Anything else in a reply is dropped.
MODEL_FILES = ("instruction.md", "environment/Dockerfile", "solution/solve.sh", "tests/test_outputs.py")
MODEL_DIRS = ("environment/",)

HARBOR_CONTRACT = """\
How the task is run (Harbor / Terminal-Bench 2):
- The image is built from environment/Dockerfile with environment/ as the build context.
  It must use a Debian/Ubuntu base (the verifier runs apt-get), pinned by tag, with WORKDIR /app.
- The agent gets a shell in that container plus instruction.md. It never sees solution/ or tests/.
- The oracle check copies solution/ to /solution and runs `bash /solution/solve.sh` as root
  in a fresh container. It must finish in well under 10 minutes.
- The agent and solve.sh run with NO network access: install every package the solution needs
  in the Dockerfile. Tests (test.sh) do have network access.
- The verifier then copies tests/ to /tests and runs pytest on /tests/test_outputs.py with a
  separate uv-managed Python 3 that has ONLY pytest installed. So test_outputs.py may import
  the standard library and pytest only. To check things inside the image (programs, services,
  databases, compiled binaries), call them with subprocess. Tests run as root from WORKDIR.
- Inside tests, a bare `python3` is the verifier's uv Python (pytest only, none of the image's
  packages). To run code that needs the image's packages, call the image's interpreter by full
  path (e.g. /usr/local/bin/python3 on python:* images, /usr/bin/python3 on ubuntu/debian).
- Harbor starts the container with `sleep infinity`: the Dockerfile's CMD/ENTRYPOINT never run,
  so no service or daemon is running when the agent starts. instruction.md must not claim one
  is. If a service is needed, the agent (and solve.sh) start it; tests may start it too.
- Commands can print nothing on success (e.g. `sqlite3 -json` on zero rows). Test helpers must
  handle empty output instead of crashing on it.
- A task passes when every test passes. The unsolved container (no agent action) must FAIL
  at least one test, and the oracle-solved container must pass ALL tests.
"""

# The difficulty lever, kept separate so a control run can leave it out
# (see CONTROL_SYSTEMS below and pipeline.py --control).
DIFFICULTY_RULE = f"""\
- Difficulty target: a strong AI agent (it reads files, greps, runs builds and tests well)
  should solve it only SOMETIMES (roughly 1-3 times in 5). Earlier tasks were far too easy:
  the agent found every fault within its first 3 commands and finished in 4-9 steps, because
  the instruction named the broken file, one `cat` showed the whole environment, the error
  message named the fault, and each fix was a 1-4 line sed. Avoid all of that. Use these knobs:
  * Where difficulty comes from (measured on the reference agent): it solves anything whose fix
    an expert can NAME in a few words ("normalize to NFC everywhere", "parameterize the query"),
    even with no hints, and it finds every inconsistency between code paths by reading. Build the
    task around a defect that shows only in BEHAVIOUR OVER A SEQUENCE (a second run after an edit,
    a resume after interruption, a retry after a partial write, late or duplicate events), where
    each function is locally correct. To stay fair:
    - instruction.md STATES the invariant over sequences ("a resumed run produces exactly what an
      uninterrupted run would", "after any edit, an incremental build equals a clean build").
      Tests choose which sequences to try; those may stay hidden. Hidden inputs, never hidden rules.
    - Every condition a test uses can be produced deterministically with something in the
      environment (a documented flag, a fake clock, a scripted input order, a crash-injection
      setting). No races, timing or sleeps.
    - The required end result is unambiguous. The difficulty is in reasoning out every sequence
      that breaks it, not in guessing what the result should be.
  * Symptom, not location: instruction.md describes what the user sees and the exact goal and
    success criteria, never which file, component or mechanism is at fault. Bad: "inspect
    /app/migrate_v2.sh", "the libraries disagree on the Vec3 type". Good: "the monthly totals in
    report.csv are wrong since the last deploy; make them correct".
    Give REQUIREMENTS (what must be true) and SYMPTOMS (what the user sees), never a DIAGNOSIS
    (why it is broken). Example for an inventory report:
      requirement: "stock_report.csv must list every warehouse with its total units on hand"
      symptom:     "two warehouses are missing and several totals are lower than the counts
                    in the inventory system"
      diagnosis (forbidden): "the join drops warehouses whose IDs have trailing spaces, and
                    returned items are subtracted twice"
  * {MIN_FAULTS} to {MAX_FAULTS} DIFFERENT faults, in at least {MIN_FAULT_LAYERS} layers (build, code, config, data, runtime),
    chained: fixing one reveals the next (builds -> runs but wrong -> edge case wrong).
    Not one fault repeated in several files.
  * Indirect symptoms: wrong numbers, silent data issues, failures only on some inputs.
    Errors must not name the faulty file or symbol.
  * Realistic size: a real project layout with at least ~{MIN_ENV_LINES} lines of source/config across
    many files, so the agent must search. Include at least one plausible but innocent decoy:
    a real module or setting that is used and correct, never one labelled "legacy", "unused" or
    "not loaded". Generate bulky data at build time.
  * Domain knowledge, not proofreading: each faulty spot must read as correct code to someone who
    does not know what correct code in this domain must do. Comments, docstrings and the README
    describe what the code DOES; they never state the rule the code breaks, never call a setting
    a workaround, never flag a line.
  * Partial fixes fail: the complete fix spans several places. For every fault there is a
    plausible but incomplete fix (fix it at one entry point but not the others, handle the
    common form but not the rare one) that passes the obvious checks, and a test the agent
    cannot see that catches it. The agent's own re-test must not catch the partial fix: after
    the obvious fix, re-running the scenario instruction.md describes works. The counterexample
    uses a different sequence, timing or input (run it twice, interrupt it midway, apply the
    change after the first pass) that the agent only tries if it reasons about the whole lifecycle.
  * No reference copies: the environment must not contain the answer elsewhere. No .git
    history, no pristine installed copy or vendored original of the faulty code, no backup or
    .orig files, no project tests that name or pin the fault. The agent has no network access.
  * Hidden edge cases: tests also check cases the visible symptom doesn't show (empty input,
    NULLs, timezones, duplicates), each following from a requirement stated in instruction.md.
    Don't paste expected outputs into instruction.md; state the rule that produces them.
  * A problem, not a guide: spend instruction.md's detail on the DELIVERABLE (output paths,
    formats, the rules that define correct results, constraints grading needs; use placeholders
    like <count>, not the expected values). Never: a numbered symptom per fault, how many things
    are wrong, the categories of faults ("currency, timezone and refund handling"), where answers
    or rules are documented, what the tests check, a command to check progress, "only change X"
    scope limits, or exact expected outputs beyond trivial ones.
  * Spaced discovery: no fault findable before agent step {CRITIC_FOUND_WITHIN}, and faults found one
    at a time: at least {DISCOVERY["min_gap"]} steps between consecutive finds, ideally about {DISCOVERY["hard_gap"] + 1}
    (hard) to {DISCOVERY["too_hard_above"]} (very hard). Never let one file or error reveal several faults at once.
  * Bespoke, not textbook: no famous bugs (Pillow ANTIALIAS, nginx trailing slash, INSERT
    without column list). Use domain logic specific to this scenario.
  * Never get difficulty from ambiguity, trick wording or hidden requirements: every test must
    follow from instruction.md plus what the agent can discover in the environment.
"""

# Extra spec fields that make the model commit to a difficulty profile. Checked in code by
# difficulty.spec_gate(); left out for the control arm together with DIFFICULTY_RULE.
DIFFICULTY_SPEC_FIELDS = """,
  "faults": [{"layer": "build|code|config|data|runtime", "where": "file or component",
              "what": "the defect", "symptom": "what the agent observes",
              "how_discovered": "what the agent must do to find it",
              "depends_on": "index of the fault that hides this one, or null",
              "discovered_at_step": "agent step at which a strong agent would find it (number)",
              "wrong_fix": "the plausible but incomplete fix a strong agent would try first",
              "counterexample": "the exact input or sequence of operations on which wrong_fix gives a wrong result",
              "why_normal_case_passes": "why the obvious checks do not reveal wrong_fix",
              "caught_by_test": "the hidden test that runs the counterexample and fails wrong_fix"}],
  "decoys": ["plausible but innocent suspects in the environment"],
  "hidden_edge_cases": ["cases the tests check that the visible symptom does not show"],
  "why_not_textbook": "why this cannot be solved from memory of a well-known bug",
  "static_read": "what reading the code alone reveals, and why that is not enough to fix everything",
  "crux": "the domain insight the complete fix depends on",
  "challenge_kind": "incremental_state|resume_after_interruption|retry_idempotency|ordering_and_duplicates|cache_invalidation|format_migration|streaming_boundaries|other",
  "sequence_invariant": "the invariant over sequences, as instruction.md states it",
  "nameable_fix": "the shortest phrase an expert would use for the whole fix",
  "self_check_blind_spot": "the re-test the agent will naturally run, and why the partial fix passes it",
  "expected_agent_steps": number"""

QUALITY_RULES = """\
Rules for a good task:
- Novel: an original scenario. Do not reproduce well-known benchmark tasks (fixing a detached
  git HEAD, chess best move, self-signed openssl cert, log summary by date range, etc.).
- Realistic and multi-step: the agent must explore the environment, diagnose, and fix or build
  something. Real failure modes (cryptic errors, dependency problems, misconfiguration) are good.
  Hard but fair: an expert reading instruction.md and exploring the container can solve it.
""" + DIFFICULTY_RULE + """\
- Deterministic: fixed data, seeds and dates. No network access needed at test time.
  Everything the task needs is installed in the Dockerfile.
- No answer leaks: the expected answer or the fix must not be readable in the image. If data is
  generated at build time, delete the generator script afterwards. Never COPY solutions or
  expected outputs into the image.
- Tests check real end state (program output, file contents, service behaviour), not superficial
  strings an agent could fake. Prefer several focused tests over one big one. Recompute expected
  values from first principles or compare to hard-coded known-good values.
- Tests exercise the REPAIRED PROGRAM, not only the shipped data: give each test fresh, isolated
  state where it can, run at least one input that is not in the shipped data, work out expected
  values independently (by hand or a small separate computation; never by copying the code being
  fixed), and make sure a solution that outputs nothing, deletes everything or hard-codes the
  shipped fixtures cannot pass.
- Tests check MEANING, not spelling. Any correct solution must pass: resolve a link and compare
  the destination instead of counting "../"; parse numbers, dates, JSON and paths instead of
  comparing their text; accept equivalent forms (trailing slash or not, 1.0 vs 1, key order,
  whitespace). A test may require an exact textual form ONLY if instruction.md states that form.
  Bad: `assert href.count('../') == 2`. Good: `assert resolve(page, href) == site_root`.
- instruction.md states exactly what is checked: paths, formats, commands, ports. Every test must
  correspond to a requirement written in instruction.md. Write it like a colleague asking for
  help: concrete, 80-300 words, no hints about the hidden bug's location, no mention of tests.
- Keep the design hidden: instruction.md and every environment/ file are what the solving agent
  sees. Never write spec details there: no fault numbers, step estimates, "decoy" or "red herring"
  labels, and no comments marking bugs as intentional, planted or injected. Faulty code must look
  like ordinary code written by a developer who made mistakes.
- solve.sh is a bash script with `set -euo pipefail`, deterministic, and actually performs the
  fix the way an expert would (no reading of tests).
"""

SPEC_SYSTEM = f"""\
You design tasks for Terminal-Bench 2, a benchmark of hard, realistic terminal work for AI agents.

{HARBOR_CONTRACT}
{QUALITY_RULES}
Reply with ONE JSON object and nothing else, with these keys:
{{
  "name": "kebab-case task name, 3-6 words, max 40 chars",
  "description": "one sentence: what the task evaluates",
  "difficulty": "medium" or "hard",
  "category": "e.g. software-engineering, system-administration, data-processing, debugging, security",
  "tags": ["3-6 short tags"],
  "expert_time_estimate_min": number,
  "junior_time_estimate_min": number,
  "base_image": "pinned Debian/Ubuntu-based image, e.g. python:3.12-slim-bookworm or ubuntu:24.04",
  "scenario": "the story and the situation the agent finds itself in",
  "environment_setup": "exactly what the Dockerfile builds: files, programs, services, data, and what is broken",
  "instruction_summary": "what instruction.md will ask for, including exact paths and formats",
  "solution_outline": ["ordered steps solve.sh performs"],
  "test_plan": ["each test: what it checks and how (commands, files, expected values)"],
  "anti_cheat": "why the answer is not visible in the image and why tests cannot be gamed",
  "failure_modes": "where a capable agent is likely to go wrong, and why that is the agent's fault"{DIFFICULTY_SPEC_FIELDS}
}}
"""


def spec_user(topic: str, calibration: str = "") -> str:
    return f"Design one task on this topic:\n\n{topic}\n" + (f"\n{calibration}\n" if calibration else "")


def calibration_block(history: list[dict]) -> str:
    """Recent band-eval verdicts, so the next design aims at the 1-3/5 band."""
    if not history:
        return ""
    lines = ["Calibration: recent tasks and how often the reference agent solved them "
             "(target: 1-3 of 5 runs)."]
    for h in history:
        note = f" ({h['note']})" if h.get("note") else ""
        lines.append(f"- {h['name']} [{h.get('difficulty', '?')}]: {h['passes']}/{h['n']} "
                     f"-> {h['verdict']}{note}. {h.get('description', '')}")
    lines.append("Design this task harder than the too_easy ones and easier than the too_hard ones.")
    return "\n".join(lines)


TRIAGE_SYSTEM = """\
You review a failed attempt by an AI agent on a Terminal-Bench 2 task and decide whose fault
the failure is.

- "model": the task was fair and the agent went wrong (wrong diagnosis, gave up, broke something,
  missed a requirement that instruction.md states clearly, ran out of ideas).
- "task": the failure comes from the task itself (instruction.md is ambiguous or contradicts
  the tests, a test checks something never asked for, the environment is broken or
  nondeterministic, the expected answer is wrong).

- "unknown": the evidence given cannot tell these apart (the trajectory tail does not show what
  the agent changed, the verifier output is missing or cut off, infrastructure may have failed).
  Do not guess "model" to fill a gap: an unexplained failure blocks the task from being kept.

Be strict about "task": only choose it when you can point to the specific flaw. Be equally
strict about "model": cite the requirement the agent missed and what it did instead.
Reply with ONE JSON object and nothing else:
{"fault": "model" or "task" or "unknown", "category": "short label, e.g. wrong-diagnosis,
 incomplete-fix, gave-up, broke-something, ambiguous-spec, untested-requirement, broken-env",
 "reason": "one sentence, concrete",
 "evidence": ["specific observations from the verifier output or trajectory"],
 "failed_requirements": ["the requirement(s) from instruction.md the run did not meet"]}
"""


def triage_user(instruction: str, tests: str, test_output: str, trajectory_tail: str) -> str:
    return (f"instruction.md:\n{instruction}\n\ntests/test_outputs.py:\n{tests}\n\n"
            f"Verifier output for this attempt:\n{test_output}\n\n"
            f"Last steps of the agent's trajectory:\n{trajectory_tail}\n")


PROJECT_SYSTEM = f"""\
You write the project inside a Terminal-Bench 2 task's environment, from a task spec.

{HARBOR_CONTRACT}
{QUALITY_RULES}
Write every file of the project under environment/ EXCEPT environment/Dockerfile: source code,
build files, configs, docs, and build-time data generators, with the spec's faults and decoys
planted exactly as described. Do NOT write environment/Dockerfile, instruction.md, solve.sh or
tests; they are written next, against your files. Generate bulky data with a script (run at
build time) instead of pasting it.

Reply in exactly this format, nothing before or after. First a manifest of EVERY path you will
write, one per line; then one block per file, each complete:

<<<MANIFEST>>>
environment/src/main.c
environment/config/app.yaml
<<<END>>>
<<<FILE environment/src/main.c>>>
...content...
<<<END>>>

If the files don't all fit in one reply, write as many COMPLETE files as fit; you will be asked
for the rest.
"""


def project_user(spec: dict) -> str:
    return "Task spec:\n\n" + json.dumps(spec, indent=2) + "\n\nWrite the project files now.\n"


def project_continue_user(spec: dict, written: list[str], missing: list[str]) -> str:
    return ("Task spec:\n\n" + json.dumps(spec, indent=2)
            + "\n\nAlready written (do not repeat): " + ", ".join(written)
            + "\n\nStill missing from your manifest, write these now, each complete:\n"
            + "\n".join(missing) + "\n\nReply with <<<FILE path>>> ... <<<END>>> blocks only.\n")


FILES_SYSTEM = f"""\
You write the remaining Terminal-Bench 2 task files from a task spec. The project under
environment/ is already written (given below); write the files that wrap it.

{HARBOR_CONTRACT}
{QUALITY_RULES}
Write exactly these files (you may also add or replace files under environment/ if the project
needs a fix to match the spec):
- instruction.md
- environment/Dockerfile (COPY the project files it needs; every COPY source must exist)
- solution/solve.sh
- tests/test_outputs.py

Do NOT write task.toml or tests/test.sh, and do not add canary comments; those are added for you.
Keep files reasonably small: generate large data with a script at build time instead of
pasting it, and remove that script in the same RUN step.

Reply with file blocks only, in exactly this format, nothing before or after:

<<<FILE instruction.md>>>
...content...
<<<END>>>
<<<FILE environment/Dockerfile>>>
...content...
<<<END>>>
"""


def files_user(spec: dict, project: dict[str, str] | None = None, max_chars: int = 150_000) -> str:
    parts = ["Task spec:\n\n" + json.dumps(spec, indent=2)]
    if project:
        parts.append("\nProject files already written under environment/:\n")
        used = 0
        for path in sorted(project):
            body = project[path]
            if used + len(body) > max_chars:  # very large projects: list the rest by name
                parts.append(f"<<<FILE {path}>>> ({len(body.splitlines())} lines, not shown)")
                continue
            used += len(body)
            parts.append(f"<<<FILE {path}>>>\n{body}<<<END>>>")
    parts.append("\nWrite the task files now.\n")
    return "\n".join(parts)


REPAIR_SYSTEM = f"""\
You fix Terminal-Bench 2 task files that failed an automatic check.

{HARBOR_CONTRACT}
{QUALITY_RULES}
Find the root cause from the error output, then fix it while keeping the task's intent and
difficulty. Do not weaken tests just to make them pass; fix the environment, solution or test
logic that is actually wrong. If the unsolved container passes the tests, make the tests check
the real required change (or make sure the environment really starts broken).

You may only change: instruction.md, environment/** , solution/solve.sh, tests/test_outputs.py.
Reply with file blocks for the files you change, each with its FULL new content, in this format,
nothing before or after:

<<<FILE path>>>
...full content...
<<<END>>>
"""


CRITIC_SYSTEM = f"""\
You are a red-team reviewer for Terminal-Bench 2 task designs. The reference agent is strong:
it reads files, greps, runs builds and tests, and earlier tasks fell to it within 3 commands.

{DIFFICULTY_RULE}
Given a task spec (JSON), walk through how that agent would solve it, step by step, starting
from instruction.md and the environment. For each fault, note the step at which it would be
found and from what. The spec is too easy if any fault is found within the agent's first
{CRITIC_FOUND_WITHIN} commands, if an error message names a faulty file or symbol, if instruction.md would name
the faulty location, if any fault is a well-known textbook bug, if there are fewer than
{MIN_FAULTS} or more than {MAX_FAULTS} different chained faults, if any comment, docstring or README line
states the rule a fault breaks, if any fault's `wrong_fix` would pass every test, if the
environment holds a reference copy of the correct code (git history, an installed original,
backups, project tests naming the fault), if `nameable_fix` alone is enough to solve it (the fix
is a named technique applied mechanically), or if a fault's counterexample is the same scenario
instruction.md describes (the agent's own re-test would catch it). It is UNFAIR if the sequence
invariant is not stated in instruction.md, or a test's condition cannot be produced
deterministically with something in the environment.

Also estimate, for every fault, `discovered_at_step`: the agent step at which it would be found.
Grade the spacing between consecutive finds: any gap below {DISCOVERY["min_gap"]} steps (two faults
falling to the same look) or a first find before step {CRITIC_FOUND_WITHIN} is TOO EASY; a median gap
of {DISCOVERY["min_gap"]}-{DISCOVERY["hard_gap"]} is moderate, about {DISCOVERY["hard_gap"] + 1} is HARD (the target),
about {DISCOVERY["too_hard_above"]} is VERY HARD, and above {DISCOVERY["too_hard_above"]} is too hard. If it is too easy,
rewrite the spec to fix every problem while keeping it fair, solvable, deterministic and on the same
topic, and put your step estimates in the revised spec's faults.

The revised spec must keep every key of the original AND include these difficulty-profile
keys, filled in (add them if the original lacks them):
{{{DIFFICULTY_SPEC_FIELDS.lstrip(",")}
}}

Reply with ONE JSON object and nothing else:
{{"walkthrough": ["step-by-step solve of the ORIGINAL spec"],
  "too_easy_because": ["problems found, empty if none"],
  "spec": {{...the full spec, revised if needed, with every key of the original...}}}}
"""


INSTRUCTION_REVIEW_SYSTEM = """\
You review instruction.md of a Terminal-Bench 2 task before it is built. The agent solving the
task sees only instruction.md and the environment; the faults below are hidden from it.

A good instruction states a PROBLEM in user terms plus the DELIVERABLE: output paths, formats,
the rules that define correct results, and constraints the grading needs. It must NOT guide the
agent. Flag and remove any of these:
  1. diagnosis: WHY something is broken or WHERE (file, component, setting, mechanism)
  2. a numbered or bulleted symptom per fault (reveals how many problems and where each lives)
  3. the number of problems, or the categories of faults ("currency, timezone, refund handling")
  4. pointers to where answers or rules live ("see docs/", "inspect migrate.sh")
  5. what the tests or verification check
  6. a command to check progress ("run pytest to check")
  7. scope narrowing ("only change the Makefile") unless the tests require it
  8. exact expected outputs or values beyond trivial ones (state the rule; use placeholders)
Also check tests/test_outputs.py the other way round: if a test requires an exact textual form
(a specific spelling, trailing slash, number of "../", key order, whitespace) that instruction.md
does not state, report it as "UNSTATED FORMAT: <test> requires <form>" in the leak list. Do not
rewrite the tests; the instruction may only be extended with that requirement if it is a real
rule of the deliverable, otherwise the test is the problem and must be reported.
Example for an inventory report:
  ok:        "stock_report.csv is wrong: some warehouses are missing and totals don't match the
             inventory system. It must list every warehouse with its total units on hand."
  forbidden: "1. two warehouses are missing (the join drops IDs with trailing spaces) 2. returns
             are double-counted. Check docs/rules.md; expected total for WH-7 is 1,204."

Check every sentence against the hidden faults and this list. If nothing violates it, reply exactly:
VERDICT: clean

Otherwise reply:
VERDICT: leaks
- <the leaking sentence> -> <which fault it reveals>
<<<FILE instruction.md>>>
...the full rewritten instruction.md...
<<<END>>>

The rewrite must keep every requirement, path, format and rule the tests rely on
(tests/test_outputs.py is given), so a correct solution can still be derived from it alone. It
should read as one problem statement plus the deliverable spec, in the same voice; it may be
shorter.
"""


def instruction_review_user(instruction: str, faults: list, tests: str) -> str:
    return ("Hidden faults (never reveal these):\n" + json.dumps(faults, indent=2)
            + "\n\ntests/test_outputs.py (keep everything these rely on):\n" + tests[:8000]
            + "\n\ninstruction.md to review:\n" + instruction)


MUTANT_SYSTEM = """\
You write deliberately INCOMPLETE solutions for a Terminal-Bench 2 task, to check that its
tests catch plausible partial fixes. You get the task's faults (each with `wrong_fix`, the
plausible incomplete fix, and its `counterexample`) and the correct solution/solve.sh.

For each fault, write a complete alternative solve script that does everything the correct
solve.sh does, EXCEPT that for this one fault it applies `wrong_fix` instead of the correct fix.
Keep every other step identical, so the only difference is that one fault's partial fix. The
script must run without errors (bash, `set -euo pipefail`); it must not break unrelated things.

Reply with one block per fault, nothing before or after, named by the fault's index:
<<<FILE mutants/0.sh>>>
...complete script...
<<<END>>>
"""


def mutants_user(faults: list, solve_sh: str) -> str:
    keep = ("where", "what", "wrong_fix", "counterexample")
    return ("Faults:\n" + json.dumps([{"index": i, **{k: f.get(k) for k in keep}}
                                      for i, f in enumerate(faults) if isinstance(f, dict)], indent=2)
            + "\n\nCorrect solution/solve.sh:\n" + solve_sh + "\n\nWrite the mutant scripts now.\n")


def critic_user(spec: dict) -> str:
    return "Task spec to review:\n\n" + json.dumps(spec, indent=2) + "\n"


def spec_retry_user(topic: str, calibration: str, problems: list[str]) -> str:
    return (spec_user(topic, calibration) + "\nYour previous design was rejected by automatic "
            "checks:\n- " + "\n- ".join(problems) + "\nDesign it again, fixing all of these.\n")


SYSTEMS = {"spec": SPEC_SYSTEM, "project": PROJECT_SYSTEM, "files": FILES_SYSTEM, "repair": REPAIR_SYSTEM}
# Control arm for A/B checks of the difficulty levers: same prompts minus DIFFICULTY_RULE and
# the difficulty profile fields (generate.py also skips the critic and gates for it). The
# Harbor runtime facts stay, since they are correctness fixes, not difficulty levers.
CONTROL_SYSTEMS = {k: v.replace(DIFFICULTY_RULE, "").replace(DIFFICULTY_SPEC_FIELDS, "")
                   for k, v in SYSTEMS.items()}
assert all(DIFFICULTY_RULE not in v and DIFFICULTY_SPEC_FIELDS not in v for v in CONTROL_SYSTEMS.values())


def repair_user(spec: dict, files: dict[str, str], error: str) -> str:
    parts = ["Task spec:\n\n" + json.dumps(spec, indent=2), "\nCurrent files:\n"]
    for path in sorted(files):
        parts.append(f"<<<FILE {path}>>>\n{files[path]}<<<END>>>")
    parts.append("\nFailed check output:\n\n" + error)
    parts.append("\nReturn the fixed files.")
    return "\n".join(parts)
