"""
Prompts for the authoring model. Three calls:

  1. SPEC   – design the task (JSON, no code)
  2. FILES  – write the task files from the spec (file blocks)
  3. REPAIR – fix the files after a failed check (file blocks, changed files only)

task.toml, tests/test.sh and the canary are written by Python, so the model
never sees or edits them.
"""

import json
import re

from config import MAX_FAULTS, MAX_RULES, MAX_SITES, MIN_FAULT_LAYERS, MIN_FAULTS, MIN_RULES, MIN_SITES, MIN_THEMES

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
- The agent may leave its own server or daemon running when it finishes (a `kill` of a shell job
  does not always kill the child). A test that starts a service must first stop anything already
  listening on that port (walk /proc/net/tcp and /proc/*/fd, or try a bind) and FAIL LOUDLY if
  the port cannot be bound, never silently talk to a stale server. (Two correct fixes failed this
  way once: the fixture deleted the database and then queried the agent's orphaned server.)
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
  * A SUBSTANTIAL working starter (several hundred lines: options, formats, edge handling, a
    second command or mode) that the instruction does not enumerate, plus one stated rule:
    "everything the tool does today must keep working". Hidden regression tests check that
    existing behaviour, so a rewrite from the rules alone drops features and fails, while a
    careful change must first understand the code. (A 120-line starter was rewritten from
    scratch by every run and added no difficulty.) No comment in the starter mentions the rules.
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
  "starter": "what the shipped starter code does (works, with default behaviours), its size and modes",
  "preserved_behaviours": [{"behaviour": "an existing behaviour the instruction does not enumerate but 'keep everything working' covers",
                            "hidden_test_input": "the input whose output must stay the same"}],
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
        by_kind.setdefault(f"{h.get('genre') or 'spec'}/{h.get('challenge_kind') or 'other'}", []).append(f"{h['passes']}/{h['n']}")
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
implementation, tests), or if the starter is small enough that rewriting it from the rules is
cheaper than changing it (fewer than about 3 preserved behaviours). It is UNFAIR if a rule is vague or ambiguous (two reasonable readings
with different outputs), if a test would check something no rule states (an unstated format,
a magic value), or if a test input cannot be produced deterministically.

If results of earlier designs are given, a design that repeats a shape those results show was
too easy is too easy. If it is too easy or unfair, rewrite the spec to fix every problem while keeping it fair,
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


def instruction_review_user(instruction: str, requirements: list, tests: str, crux: str = "", genre: str = "spec") -> str:
    head = ("Requirements the tests check (each must be stated in instruction.md):\n" if genre == "spec"
            else "Hidden faults / sites (never reveal these):\n")
    return (head + json.dumps(requirements, indent=2)
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


def critic_user(spec: dict, calibration: str = "") -> str:
    return ("Task spec to review:\n\n" + json.dumps(spec, indent=2) + "\n"
            + (f"\nResults of earlier designs under these rules:\n{calibration}\n" if calibration else ""))


POSTMORTEM_SYSTEM = """\
You write the lesson from one evaluated Terminal-Bench 2 task, for the designer of the next one.
You get the design (rules or faults), the mutation check (which incomplete solutions the tests
caught), and every agent run: pass or fail, steps, failed tests, and the triage reason.

Say in 2-3 plain sentences WHY the task landed where it did: which rules or faults every run got
right and how (read from the code, derived from the goal, tested itself), which ones caused
failures, and what the next design should do differently (more independent rules on new themes,
sharper hidden inputs, a different kind) or keep. Be concrete; name the rules or tests.

Reply with ONE JSON object and nothing else:
{"lesson": "2-3 sentences", "held": ["rules/faults every run got right"], "failed": ["rules/faults that caused failures"]}
"""


def postmortem_user(spec: dict, mutation: list, trials: list, triage: list) -> str:
    design = {"name": spec.get("name"), "challenge_kind": spec.get("challenge_kind"),
              "requirements": [{"id": r.get("id"), "rule": str(r.get("rule"))[:160], "theme": r.get("theme")}
                               for r in spec.get("requirements") or [] if isinstance(r, dict)],
              "faults": [str(f.get("what"))[:160] for f in spec.get("faults") or [] if isinstance(f, dict)]}
    runs = [{"outcome": t.get("outcome"), "steps": t.get("episodes"), "failed_tests": t.get("failed_tests"),
             "first_touched_fix_files_at_step": t.get("found_step")} for t in trials]
    return ("Design:\n" + json.dumps(design, indent=1) + "\n\nMutation check (incomplete solutions vs the tests):\n"
            + json.dumps([{k: m.get(k) for k in ("fault", "verdict")} for m in mutation or []])
            + "\n\nAgent runs:\n" + json.dumps(runs, indent=1) + "\n\nTriage of failures:\n"
            + json.dumps([{k: f.get(k) for k in ("trial", "fault", "category", "reason")} for f in triage or []], indent=1) + "\n")


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


# ---------------------------------------------------------------------------------------------
# Other genres, chosen per topic with a [genre] tag on the topic line. "spec" (above) is the
# default. "hidden_fault" is the retired bug-hunt genre (every such task scored 4-5/5), kept so a
# batch can sprinkle a few in and measure them. "judgement" is the shape of the one fair failure.

DIFFICULTY_RULE_FAULT = f"""\
- Difficulty target: a strong AI agent (it reads files, greps, runs builds and tests well)
  should solve it only SOMETIMES (roughly 1-3 times in 5). Every earlier task was solved 4-5/5:
  the agent found the faults by reading and their fixes were named techniques. Adding more
  faults, more code or more steps did not change that; the SHAPE of the problem does:
  * Where difficulty comes from (measured on the reference agent): it solves anything whose fix
    an expert can NAME in a few words ("normalize to NFC everywhere", "parameterize the query"),
    even with no hints, and it finds every inconsistency between code paths by reading. Build the
    task around a defect that shows only in BEHAVIOUR OVER A SEQUENCE (a second run after an edit,
    a resume after interruption, a retry after a partial write, late or duplicate events), where
    each function is locally correct.
    - NO SINGLE FUNCTION, read against the goal, reveals the fault. A task whose bug can be read off
      one function (a delta computed from the wrong baseline, a check placed after a write) was
      solved 4-5/5 in ~10 steps even with no hints and no reference code. The defect must live in
      the INTERACTION: state written by one component or run and read by another under a different
      assumption (a manifest that omits an input the renderer uses, a checkpoint that saves the
      cursor but not the dedup set, a cache key built in one module and looked up in another).
      Each side is correct on its own; only tracing the data across them shows the bug.
    To stay fair:
    - instruction.md STATES the invariant over sequences ("a resumed run produces exactly what an
      uninterrupted run would", "after any edit, an incremental build equals a clean build").
      Tests choose which sequences to try; those may stay hidden. Hidden inputs, never hidden rules.
      Pick them where partial fixes break, not where an agent would first look: non-round values,
      boundaries (first and last item, exactly on a tie), the crash path, twice in a row. A test
      that only uses the obvious values (50, 100) is no stronger than the agent's own re-test.
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
  * ONE central challenge with {MIN_FAULTS} to {MAX_FAULTS} DIFFERENT faults that all serve it: interacting
    requirements, where fixing one exposes the next. No unrelated faults to pad the count (a
    typo in a wrapper script, a wrong interpreter path, a function that is never called, a wrong
    config path): they add steps, not difficulty. Not one fault repeated in several files.
  * Indirect symptoms: wrong numbers, silent data issues, failures only on some inputs.
    Errors must not name the faulty file or symbol.
  * Realistic size: a real project as big as the scenario needs, with no line target. No padding and no decoy modules: ordinary, correct code around the faults is
    enough. Never label code "legacy", "unused" or "not loaded". Generate bulky data at build time.
  * Domain knowledge, not proofreading: each faulty spot must read as correct code to someone who
    does not know what correct code in this domain must do. Comments, docstrings and the README
    describe what the code DOES; they never state the rule the code breaks, never call a setting
    a workaround, never flag a line.
  * Partial fixes fail: the complete fix spans several places. For each central fault (at least 2) there is a
    plausible but incomplete fix (fix it at one entry point but not the others, handle the
    common form but not the rare one) that passes the obvious checks, and a test the agent
    cannot see that catches it. The agent's own re-test must not catch the partial fix: after
    the obvious fix, re-running the scenario instruction.md describes works. The counterexample
    uses a different sequence, timing or input (run it twice, interrupt it midway, apply the
    change after the first pass) that the agent only tries if it reasons about the whole lifecycle.
  * No reference copies: the environment must not contain the answer elsewhere. No .git
    history, no pristine installed copy or vendored original of the faulty code, no backup or
    .orig files, no project tests that name or pin the fault. The agent has no network access.
    This includes the task's OWN code: if the invariant compares two paths (live vs replay,
    incremental vs full rebuild, fast vs slow), the reference path must NOT already handle the
    tricky case correctly, or the agent just copies its logic across. Either both paths share the
    flawed reasoning, or the reference is a stated behaviour the agent must reason out. README
    and docs describe usage and data formats; they may restate the stated invariant, never the
    case-level semantics a fault breaks.
  * No independent check: the agent must not be able to RUN something that computes the right
    answer and compare its output against it (a `verify` command, a full rebuild next to the
    incremental path, a replay, an import/export round-trip). Agents used such a reference to test
    their way to every hidden case (a shipped `verify`; fuzzing incremental output against a full
    rebuild). The agent may still check its work by reasoning, small hand-worked examples, and
    the stated rules; it just gets no oracle for free.
  * Hidden edge cases: tests also check cases the visible symptom doesn't show (empty input,
    NULLs, timezones, duplicates), each a CONSEQUENCE of the stated goal that an expert would
    derive, not a separately listed requirement. Don't paste expected outputs into
    instruction.md; state the rule that produces them.
  * Goal, not checklist: instruction.md states the outcome at the level a user would (the
    invariant, "after any sequence of operations the snapshot equals a replay of the log"), never
    the list of cases and steps that achieve it. Every `wrong_fix` must stay a trap: never add a
    sentence whose only purpose is to warn against one ("if an event is corrected twice, use the
    latest correction"). Never name the fix or the crux.
  * A problem, not a guide: spend instruction.md's detail on the DELIVERABLE (output paths,
    formats, the rules that define correct results, constraints grading needs; use placeholders
    like <count>, not the expected values). Never: a numbered symptom per fault, how many things
    are wrong, the categories of faults ("currency, timezone and refund handling"), where answers
    or rules are documented, what the tests check, a command to check progress, "only change X"
    scope limits, or exact expected outputs beyond trivial ones.
  * Bespoke, not textbook: no famous bugs (Pillow ANTIALIAS, nginx trailing slash, INSERT
    without column list). Use domain logic specific to this scenario.
  * Never get difficulty from ambiguity, trick wording or hidden requirements: every test must
    follow from instruction.md plus what the agent can discover in the environment.
"""


DIFFICULTY_SPEC_FIELDS_FAULT = """,
  "faults": [{"layer": "build|code|config|data|runtime", "where": "file or component",
              "what": "the defect", "symptom": "what the agent observes",
              "how_discovered": "what the agent must do to find it",
              "central": "true if this fault is part of the central challenge",
              "wrong_fix": "central faults: the plausible but incomplete fix a strong agent would try first",
              "counterexample": "the exact input or sequence of operations on which wrong_fix gives a wrong result",
              "why_normal_case_passes": "why the obvious checks do not reveal wrong_fix",
              "caught_by_test": "the hidden test that runs the counterexample and fails wrong_fix"}],
  "hidden_edge_cases": ["cases the tests check that the visible symptom does not show"],
  "why_not_textbook": "why this cannot be solved from memory of a well-known bug",
  "static_read": "what reading the code alone reveals, and why that is not enough to fix everything",
  "crux": "the domain insight the complete fix depends on",
  "challenge_kind": "incremental_state|resume_after_interruption|retry_idempotency|ordering_and_duplicates|cache_invalidation|format_migration|streaming_boundaries|other",
  "sequence_invariant": "the invariant over sequences, as instruction.md states it",
  "nameable_fix": "the shortest phrase an expert would use for the whole fix",
  "self_check_blind_spot": "the re-test the agent will naturally run, and why the partial fix passes it",
  "reference_in_environment": "any code, doc or data in the environment that already computes or states the correct handling of the tricky case; must be none",
  "interaction": "the components or runs whose interaction causes the central defect (at least 2), and why each looks correct on its own",
  "runnable_reference": "any command or code path the agent can run to get the correct answer and compare against (verify command, full rebuild, replay, round-trip); must be none"
"""


CRITIC_SYSTEM_FAULT = f"""\
You are a red-team reviewer for Terminal-Bench 2 task designs. The reference agent is strong:
it reads files, greps, runs builds and tests, and re-tests its own fixes; every earlier task fell
to it 4-5 times in 5.

{DIFFICULTY_RULE_FAULT}
Given a task spec (JSON), walk through how that agent would solve it, step by step, starting
from instruction.md and the environment. For each fault, note what reveals it and what the
agent must reason out to fix it completely. The spec is too easy if reading the code is enough
to find and fix a central fault, if an error message names a faulty file or symbol, if instruction.md would name
the faulty location, if any fault is a well-known textbook bug, if there are fewer than
{MIN_FAULTS} or more than {MAX_FAULTS} faults, if any fault is filler unrelated to the central challenge, if any comment, docstring or README line
states the rule a fault breaks, if any fault's `wrong_fix` would pass every test, if the
environment holds a reference copy of the correct code (git history, an installed original,
backups, project tests naming the fault), if `nameable_fix` alone is enough to solve it (the fix
is a named technique applied mechanically), if a fault's counterexample is the same scenario
instruction.md describes (the agent's own re-test would catch it), or if the environment already
contains correct logic for the tricky case that the agent can copy (e.g. a correct replay or
full-rebuild path that the invariant compares against), or if any central fault can be found and
fixed by reading ONE function against the goal (the defect must live in the interaction between
components or runs, with each side correct on its own), or if the agent can run something that
computes the correct answer and compare against it (a verify command, a full rebuild, a replay,
a round-trip). It is UNFAIR if the sequence
invariant is not stated in instruction.md, or a test's condition cannot be produced
deterministically with something in the environment.

If it is too easy or unfair, rewrite the spec to fix every problem while keeping it fair,
solvable, deterministic and on the same topic. Do not make it harder by adding faults, code or
steps; change what the agent has to reason about.

The revised spec must keep every key of the original AND include these difficulty-profile
keys, filled in (add them if the original lacks them):
{{{DIFFICULTY_SPEC_FIELDS_FAULT.lstrip(",")}
}}

Reply with ONE JSON object and nothing else:
{{"walkthrough": ["step-by-step solve of the ORIGINAL spec"],
  "too_easy_because": ["problems found, empty if none"],
  "spec": {{...the full spec, revised if needed, with every key of the original...}}}}
"""



INSTRUCTION_REVIEW_SYSTEM_FAULT = """\
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
  9. the fix or the crux itself (the technique, rule or insight that solves it; it is given below)
 10. a requirement whose only purpose is to warn against a fault's `wrong_fix` (e.g. "if an event
     is corrected twice, use the latest correction" when the trap is handling repeated corrections)
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

The rewrite must keep the goal (the invariant), the interface (paths, commands, ports, output
formats) and any rule the tests rely on that an expert could NOT derive from the goal, domain
knowledge and the environment. Consequences of the goal that an expert would work out (repeated
corrections, existing data, the crash path) are removed, not kept. It should read as one problem
statement plus the deliverable spec, in the same voice; it may be shorter.
"""



MUTANT_SYSTEM_FAULT = """\
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



DIFFICULTY_RULE_JUDGEMENT = f"""\
- Difficulty target: a strong AI agent (it reads files, greps, runs builds and tests well, and
  writes its own tests) should solve the task only SOMETIMES (roughly 1-3 times in 5). The only
  fair failures measured so far came from a task where the agent had to JUDGE whether its fix was
  complete: a stated property that must hold everywhere, violated at several places that differ
  in mechanism, with no tests and no oracle; the agent fixed the obvious site, re-tested the
  reported symptom, and decided the rest was unnecessary. Build that shape:
  * ONE stated property that must hold everywhere ("no user-supplied value can put a line break
    into a response header", "every monetary amount is rounded the same way at every boundary",
    "no path derived from input can leave the base directory", "every record is durable before
    its index entry"). instruction.md states the property, ONE reported symptom (the obvious
    site), and the interface. It never lists the sites, their count, or their mechanisms.
  * A realistic codebase (several modules, a real-looking library or service) that violates the
    property at {MIN_SITES} to {MAX_SITES} SITES which differ in MECHANISM: value vs name, direct
    vs through a helper, one site using a different library or API, one site reached only through
    a second entry point, one site in data already stored. Fixing one site and grepping for the
    same pattern must NOT reveal the others; knowing the domain must.
  * A partial fix (the obvious site) makes the reported symptom disappear and passes every
    check the agent would naturally run. Hidden tests probe each site with its own input.
  * No tests, no verify/check command, no reference copy, no .git, no upstream original (a
    library installed with pip is modified in place and its pristine copy removed), no comment
    that marks a site. The agent has no network access.
  * Fair: every site is a violation of the STATED property that an expert in the domain would
    recognise from the property plus reading the code; tests check behaviour through the public
    interface, never a particular patch. Where two fixes are both valid (reject a violating value
    with an error, or sanitise it and answer normally; round before or after a conversion),
    instruction.md states which one is required, with the exact observable result; a test must
    never pin one of two valid behaviours the instruction left open. (A correct fix that rejected
    CRLF input with a 400 failed tests that expected the value sanitised and the header present.)
  * The codebase is substantial and its existing behaviour matters: instruction.md says
    everything the service does today must keep working, and hidden regression tests check it,
    so "rewrite the affected module" is not a shortcut.
"""

DIFFICULTY_SPEC_FIELDS_JUDGEMENT = """,
  "challenge_kind": "property_completeness",
  "property": "the one property, as instruction.md states it",
  "reported_symptom": "the one symptom instruction.md reports (the obvious site)",
  "sites": [{"where": "file and function", "mechanism": "how this site violates the property",
             "differs_from_other_sites": "why fixing another site and searching for its pattern does not reveal this one",
             "hidden_test_input": "the input the hidden test sends through the public interface"}],
  "partial_fix": "the fix an agent makes first, and which checks it passes",
  "preserved_behaviours": [{"behaviour": "an existing behaviour that must keep working while the property is enforced",
                            "hidden_test_input": "the input whose output must stay the same"}],
  "self_check_blind_spot": "why the agent's own re-test passes after the partial fix",
  "runnable_reference": "any command or code path the agent can run to get the correct answer and compare against; must be none",
  "reference_in_environment": "any code, doc or data in the environment that already handles the property correctly or states the sites; must be none"
"""

CRITIC_SYSTEM_JUDGEMENT = """\
You are a red-team reviewer for Terminal-Bench 2 task designs. The reference agent is strong:
it reads files, greps, runs builds and tests, and writes its own tests; it fails mainly when it
must judge whether a fix is complete with nothing to check against.

__RULE__
Given a task spec (JSON), walk through how that agent would solve it: which site it finds from
the symptom, what it would grep for next, which sites that search reveals, and what it would
test. The spec is TOO EASY if two sites share a mechanism (one search finds both), if
instruction.md lists or counts the sites, if a comment or docstring marks a site, if there are
fewer than __MIN_SITES__ sites, if any test, oracle or reference copy exists, or if the fix is a
named technique applied in one place. It is UNFAIR if a site does not violate the stated
property as an expert would read it, or if a hidden test checks a particular patch rather than
behaviour through the public interface.

If results of earlier designs are given, a design that repeats a shape those results show was
too easy is too easy. If it is too easy or unfair, rewrite the spec to fix every problem while
keeping it fair, solvable, deterministic and on the same topic.

The revised spec must keep every key of the original AND include these design keys, filled in:
{__FIELDS__
}

Reply with ONE JSON object and nothing else:
{"walkthrough": ["how the agent would approach the ORIGINAL spec, site by site"],
  "too_easy_because": ["problems found, empty if none"],
  "spec": {...the full spec, revised if needed, with every key of the original...}}
"""

CRITIC_SYSTEM_JUDGEMENT = (CRITIC_SYSTEM_JUDGEMENT.replace("__RULE__", DIFFICULTY_RULE_JUDGEMENT)
                           .replace("__MIN_SITES__", str(MIN_SITES))
                           .replace("__FIELDS__", DIFFICULTY_SPEC_FIELDS_JUDGEMENT.lstrip(",")))


GENRES = {
    "spec": {"rule": DIFFICULTY_RULE, "fields": DIFFICULTY_SPEC_FIELDS, "critic": CRITIC_SYSTEM,
             "review": INSTRUCTION_REVIEW_SYSTEM, "mutants": MUTANT_SYSTEM},
    "hidden_fault": {"rule": DIFFICULTY_RULE_FAULT, "fields": DIFFICULTY_SPEC_FIELDS_FAULT, "critic": CRITIC_SYSTEM_FAULT,
                     "review": INSTRUCTION_REVIEW_SYSTEM_FAULT, "mutants": MUTANT_SYSTEM_FAULT},
    "judgement": {"rule": DIFFICULTY_RULE_JUDGEMENT, "fields": DIFFICULTY_SPEC_FIELDS_JUDGEMENT, "critic": CRITIC_SYSTEM_JUDGEMENT,
                  "review": INSTRUCTION_REVIEW_SYSTEM_FAULT, "mutants": MUTANT_SYSTEM_FAULT},
}


def split_topic(line: str) -> tuple[str, str]:
    """'[judgement] a payment service ...' -> ('judgement', 'a payment service ...'); untagged -> 'spec'."""
    m = re.match(r"\s*\[(\w+)\]\s*(.*)", line, re.S)
    if m and m.group(1).lower() in GENRES:
        return m.group(1).lower(), m.group(2).strip()
    return "spec", line.strip()


def systems_for(genre: str = "spec", control: bool = False) -> dict:
    """The stage prompts for a genre: the spec-genre texts with the design rule and spec fields
    swapped (they are embedded verbatim), plus that genre's critic, reviewer and mutant prompts.
    control=True strips the design rule and fields (the A/B control arm)."""
    g = GENRES[genre]
    out = {k: v.replace(DIFFICULTY_RULE, "" if control else g["rule"]).replace(DIFFICULTY_SPEC_FIELDS, "" if control else g["fields"])
           for k, v in SYSTEMS.items()}
    out.update(critic=g["critic"], review=g["review"], mutants=g["mutants"])
    return out


def repair_user(spec: dict, files: dict[str, str], error: str) -> str:
    parts = ["Task spec:\n\n" + json.dumps(spec, indent=2), "\nCurrent files:\n"]
    for path in sorted(files):
        parts.append(f"<<<FILE {path}>>>\n{files[path]}<<<END>>>")
    parts.append("\nFailed check output:\n\n" + error)
    parts.append("\nReturn the fixed files.")
    return "\n".join(parts)
