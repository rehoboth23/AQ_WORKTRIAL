"""
Prompts for the authoring model. Three calls:

  1. SPEC   – design the task (JSON, no code)
  2. FILES  – write the task files from the spec (file blocks)
  3. REPAIR – fix the files after a failed check (file blocks, changed files only)

task.toml, tests/test.sh and the canary are written by Python, so the model
never sees or edits them.
"""

import json

from config import MAX_RULES, MIN_RULES, MIN_THEMES

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
- Difficulty target: a strong AI agent (it reads files, greps, runs builds and tests well, and
  writes its own end-to-end tests) should solve the task only SOMETIMES (roughly 1-3 times in 5).
  Measured on ~20 tasks: every HIDDEN-FAULT task (find and fix planted bugs) was solved 4-5/5,
  in 10-35 steps, whatever was hidden, because the agent finds discrete faults by reading and
  tests every case it thinks of; a runnable oracle (a verify command, a full rebuild to compare
  against) makes it trivial. Do not design hidden-fault tasks. Design SPECIFICATION tasks:
  * The task is to BUILD or TRANSFORM to a long, explicit specification: {MIN_RULES} to {MAX_RULES}
    independent requirements, each stated precisely in instruction.md, each DIFFERENT from what a
    programmer would produce by default (the default rounding, sort, padding, date form, error
    handling, line endings...), each checked by a hidden test input that differs from any example.
    Passing needs ALL of them right; the agent only tests the rules it remembers and reads
    correctly. Difficulty comes from breadth and precision, never from hiding anything.
  * Kinds: build_from_spec (write or finish a CLI, parser, renderer or report generator to the
    rules), exact_data_transform (normalise a messy dataset to an exact output format; many
    format traps), large_corpus_migration (apply a rule set across dozens of files; partial
    completion fails).
  * Independent themes: the rules must span at least {MIN_THEMES} distinct themes (formatting,
    rounding/arithmetic, ordering and grouping, text width and Unicode, structure such as
    pagination or sections, input tolerance, error handling and exit codes, edge inputs). A set of
    rules that all follow ONE theme was solved 4/4: once the agent gets the theme, it gets them
    all. Each rule must be checkable on its own.
  * A working starter is fine and realistic: code that does the job with default behaviours
    everywhere, and no comment that mentions the rules.
  * No oracle: no sample of the expected output, no verify/check/diff/self-test command, no
    reference implementation, no tests, no backup or original in the image, and nothing the agent
    can run to get the correct answer and compare against. The agent has no network access.
  * Hidden inputs, not hidden rules: tests use inputs that differ from every example in
    instruction.md, with non-round values and boundaries (exactly-at-the-limit lengths, values
    that round differently under the default, empty groups, the last record, a page boundary).
    Every assertion follows from a stated rule; exact textual forms are tested exactly only
    because the rule states that form. Never get difficulty from ambiguity or trick wording:
    an expert reading instruction.md must be able to derive every test.
  * No reference copies of the answer anywhere in the environment (git history, an installed
    original, .orig/.bak files, a second implementation).
"""

# Extra spec fields that make the model commit to a difficulty profile. Checked in code by
# difficulty.spec_gate(); left out for the control arm together with DIFFICULTY_RULE.
DIFFICULTY_SPEC_FIELDS = """,
  "challenge_kind": "build_from_spec|exact_data_transform|large_corpus_migration",
  "requirements": [{"id": "R1", "rule": "the rule, precisely as instruction.md will state it",
                    "theme": "formatting|arithmetic|ordering|unicode_width|structure|input_tolerance|error_handling|edge_inputs|other",
                    "default_behaviour": "what a programmer produces without this rule",
                    "hidden_test_input": "the input the test uses; differs from every example in instruction.md",
                    "boundary": "the non-round value or edge the test includes"}],
  "themes": ["the distinct themes the rules cover"],
  "starter": "what the shipped starter code does (works, with default behaviours), or none",
  "self_check_blind_spot": "which rules an agent is likely to forget or misread, and why",
  "runnable_reference": "any command or code path the agent can run to get the correct answer and compare against (verify command, sample output, reference implementation); must be none",
  "reference_in_environment": "any code, doc or data in the environment that already produces or states the correct output; must be none"
"""

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
- Tests check BEHAVIOUR, not the chosen implementation: what the program does through its public
  interface ("a retried delivery leaves the balance unchanged", "two spellings log into one
  account"), never how a fix is built (a schema constraint's text, a column's existence, a
  function name, a config line). Any correct fix must pass, so tests never pin the technique.
- Fair means DERIVABLE: every test follows from instruction.md's stated goal plus what an expert
  in the domain knows and what the environment shows (including how its own code behaves). It
  need not be written out. A test that checks something an expert could NOT derive (an arbitrary
  format, a magic value, a choice between equally valid behaviours) must be stated. instruction.md
  always states the interface grading needs: paths, ports, commands, output formats. Write it
  like a colleague asking for help: concrete; the rules are the workload, so list them, numbered
  and precise; no mention of tests.
- Keep the design hidden: instruction.md and every environment/ file are what the solving agent
  sees. Never write design details there: no rule ids, test inputs, "hidden test" or "trap"
  labels, and no comment in the starter that mentions a rule. The starter must look like ordinary
  code written with default behaviours.
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
    """Recent band-eval verdicts (current design only), so the next design aims at 1-3/5."""
    if not history:
        return ""
    by_kind = {}
    for h in history:
        by_kind.setdefault(h.get("challenge_kind") or "other", []).append(f"{h['passes']}/{h['n']}")
    lines = ["Calibration: recent tasks under these rules and how often the reference agent solved them "
             "(target: 1-3 of 5 runs).",
             "Per kind: " + "; ".join(f"{k}: {len(v)} task(s), {', '.join(v)}" for k, v in sorted(by_kind.items()))]
    for h in history:
        note = f" ({h['lesson']})" if h.get("lesson") else (f" ({h['note']})" if h.get("note") else "")
        kind = f" [{h['challenge_kind']}]" if h.get("challenge_kind") else ""
        lines.append(f"- {h['name']}{kind}: {h['passes']}/{h['n']} -> {h['verdict']}{note}. {h.get('description', '')}")
    lines.append("Tasks solved too often had few rules, rules on one theme, or an oracle to compare against. "
                 "Make this design harder with more independent, precisely stated rules on more themes and "
                 "sharper hidden inputs; never by hiding rules. Make it easier than the too_hard ones.")
    return "\n".join(lines)


TRIAGE_SYSTEM = """\
You review a failed attempt by an AI agent on a Terminal-Bench 2 task and decide whose fault
the failure is.

- "model": the task was fair and the agent went wrong (wrong diagnosis, gave up, broke something,
  missed a requirement that instruction.md states clearly, ran out of ideas).
- "task": the failure comes from the task itself (instruction.md is ambiguous or contradicts
  the tests, a test checks something an expert could not derive from instruction.md's goal plus
  domain knowledge and the environment, the environment is broken or nondeterministic, the
  expected answer is wrong).

Requirements need not be written out to be fair: if the goal is "the snapshot always equals a
replay of the log" and the agent's fix breaks when one event is corrected twice, that is the
model's fault (it missed a consequence of the goal), not an unstated requirement.

- "unknown": the evidence given cannot tell these apart (the trajectory tail does not show what
  the agent changed, the verifier output is missing or cut off, infrastructure may have failed).
  Do not guess "model" to fill a gap: an unexplained failure blocks the task from being kept.

Be strict about "task": only choose it when you can point to the specific flaw. Be equally
strict about "model": trace the FAILING ASSERTION to instruction.md. Quote the sentence of
instruction.md (or the fact visible in the environment, such as the program's existing output
words) that requires what the assertion checks. Test names, docstrings and comments are NOT
requirements: the agent never sees them. If no sentence or derivable consequence of the stated
goal requires what the failing assertion checks, it is "task" (a test checking an unstated
choice), even if every other test passed. Example: the goal is "each event affects the balance
exactly once"; the failing assertion requires the receiver to print "duplicate" for a retry; the
balance was correct; nothing asks for that output -> "task".
Reply with ONE JSON object and nothing else:
{"fault": "model" or "task" or "unknown", "category": "short label, e.g. wrong-diagnosis,
 incomplete-fix, gave-up, broke-something, ambiguous-spec, untested-requirement, broken-env",
 "reason": "one sentence, concrete",
 "evidence": ["specific observations from the verifier output or trajectory"],
 "failed_requirements": ["the requirement(s) from instruction.md the run did not meet"],
 "requirement_quote": "for 'model': the exact instruction.md sentence (or environment fact) the failing assertion enforces; empty otherwise"}
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
it reads files, greps, runs builds and tests, and writes its own end-to-end tests; every
hidden-fault task fell to it 4-5 times in 5.

{DIFFICULTY_RULE}
Given a task spec (JSON), walk through how that agent would solve it: which rules it would get
right on the first pass, which it would misread or forget, and what it would test itself. The
spec is TOO EASY if it has fewer than {MIN_RULES} requirements, if the rules cover fewer than
{MIN_THEMES} themes or mostly follow one theme, if any rule matches the default behaviour (no
deviation to get wrong), if several rules are the same rule restated, if the hidden test inputs
are covered by examples in instruction.md, or if anything in the environment or instruction
gives the agent an oracle (expected output, a verify/check/diff command, a reference
implementation, tests). It is UNFAIR if a rule is vague or ambiguous (two reasonable readings
with different outputs), if a test would check something no rule states (an unstated format,
a magic value), or if a test input cannot be produced deterministically.

If it is too easy or unfair, rewrite the spec to fix every problem while keeping it fair,
solvable, deterministic and on the same topic: add independent rules on new themes, sharpen
vague rules, move test inputs away from the examples. Do not add hidden faults.

The revised spec must keep every key of the original AND include these design keys, filled in:
{{{DIFFICULTY_SPEC_FIELDS.lstrip(",")}
}}

Reply with ONE JSON object and nothing else:
{{"walkthrough": ["how the agent would approach the ORIGINAL spec, rule by rule"],
  "too_easy_because": ["problems found, empty if none"],
  "spec": {{...the full spec, revised if needed, with every key of the original...}}}}
"""


INSTRUCTION_REVIEW_SYSTEM = """\
You review instruction.md of a Terminal-Bench 2 specification task before it is built. The agent
solving the task sees only instruction.md and the environment. The rules ARE the workload, so
instruction.md must state every requirement precisely; the difficulty is breadth, not hiding.

Check, against the requirement list and tests/test_outputs.py given to you:
  1. MISSING RULE: a requirement the tests check that instruction.md does not state, or states so
     vaguely that two reasonable readings give different outputs.
  2. LEAKED ANSWER: expected output pasted beyond trivial examples, a sample that covers the
     hidden test inputs, or a hint of what the tests check.
  3. ORACLE: any instruction to run a command whose output signals completion ("run verify until
     it reports OK", "compare with the sample") or a pointer to a reference implementation.
  4. UNSTATED FORMAT: a test requires an exact textual form (spelling, spacing, trailing slash,
     key order) that no rule states; report it as "UNSTATED FORMAT: <test> requires <form>".
Also make sure the interface is stated: the command to run, input paths and columns, output
path or stream, exit codes.

If nothing violates this, reply exactly:
VERDICT: clean

Otherwise reply:
VERDICT: leaks
- <the problem> -> <which requirement or test it concerns>
<<<FILE instruction.md>>>
...the full rewritten instruction.md...
<<<END>>>

The rewrite keeps the problem statement and the numbered rules, adds the missing or sharpened
rules, removes leaked outputs and oracle pointers, and stays in the same voice. For an UNSTATED
FORMAT, add the form as a rule only if it is a genuine part of the house style; otherwise the test
is the problem and must be reported.
"""


def instruction_review_user(instruction: str, requirements: list, tests: str, crux: str = "") -> str:
    return ("Requirements the tests check (each must be stated in instruction.md):\n" + json.dumps(requirements, indent=2)
            + "\n\ntests/test_outputs.py (keep everything these rely on):\n" + tests[:8000]
            + "\n\ninstruction.md to review:\n" + instruction)


MUTANT_SYSTEM = """\
You write deliberately INCOMPLETE solutions for a Terminal-Bench 2 specification task, to check
that its tests catch a solution that misses one rule. You get the task's requirements (each with
the default behaviour a programmer would produce without it) and the correct solution/solve.sh.

For each listed requirement, write a complete alternative solve script that does everything the
correct solve.sh does, EXCEPT that for this one requirement it produces the DEFAULT behaviour
instead. Keep every other rule implemented, so the only difference is that one rule. The script
must run without errors (bash, `set -euo pipefail`).

Reply with one block per requirement, nothing before or after, named by the requirement's index:
<<<FILE mutants/0.sh>>>
...complete script...
<<<END>>>
"""


EQUIVALENCE_SYSTEM = """\
You check whether an incomplete solution of a Terminal-Bench 2 task is really wrong. The task's
tests all passed when this incomplete solution (the "mutant") was used as the solution. Either the tests miss a case,
or the mutant is behaviourally equivalent to the correct solution (another fix covers the same
cases, so no input can tell them apart).

Compare the correct solve.sh and the mutant against instruction.md's goal. Look for ONE concrete
input or sequence of operations (files, commands, order) on which the program would behave
differently after the mutant than after the correct solution, in a way the goal makes wrong.
Only answer "equivalent" if no such case exists.

Reply with ONE JSON object and nothing else:
{"equivalent": true or false,
 "distinguishing_case": "exact steps (setup, commands, expected vs mutant result), or empty if equivalent",
 "reason": "one or two sentences"}
"""


def equivalence_user(fault: dict, instruction: str, solve_sh: str, mutant_sh: str) -> str:
    keep = ("where", "what", "wrong_fix", "counterexample")
    return ("Requirement and the incomplete solution's behaviour for it:\n" + json.dumps({k: fault.get(k) for k in keep}, indent=2)
            + "\n\ninstruction.md:\n" + instruction + "\n\nCorrect solution/solve.sh:\n" + solve_sh
            + "\n\nMutant solve.sh (all tests passed with it):\n" + mutant_sh + "\n")


def mutants_user(faults: list, solve_sh: str) -> str:
    keep = ("where", "what", "wrong_fix", "counterexample")
    return ("Requirements (what = the rule; wrong_fix = the default behaviour the mutant must produce; "
            "counterexample = the hidden input):\n" + json.dumps([{"index": i, **{k: f.get(k) for k in keep}}
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
