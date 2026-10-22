"""
Prompts for the authoring model. Three calls:

  1. SPEC   – design the task (JSON, no code)
  2. FILES  – write the task files from the spec (file blocks)
  3. REPAIR – fix the files after a failed check (file blocks, changed files only)

task.toml, tests/test.sh and the canary are written by Python, so the model
never sees or edits them.
"""

import json
import os
import re

from config import FUZZ_TESTS
from config import MAX_CHECKS, MIN_CHECKS

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
  The same goes for anything a test runs that calls python or pip itself (make, a build script):
  pass env with PATH="/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" and no VIRTUAL_ENV, or the
  child finds the verifier's uv Python, which has no pip and none of the image's packages.
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
- Difficulty target: a strong AI agent (it reads files, greps, runs builds and tests, writes its own
  tests, and runs any reference it is given) should solve the task only SOMETIMES (roughly 1-3
  times in 5). Measured on many tasks: whatever it can READ (code, a rule list, planted faults),
  already KNOWS (standards, formats) or RUN to compare against, it checks and gets right, even when
  that takes 80 steps. So difficulty must come from what the agent cannot fully check before it
  finishes: an evaluation it cannot reproduce in full.
  * The task is a realistic piece of work in the shape the topic names (rule induction from
    examples, a model or estimate scored on held-out data, a live system changed under load, a
    procedure carried out over local services, trace or concurrency debugging, a domain pipeline
    with field conventions, a port with behavioural parity, cryptanalysis from source, a
    performance target). A realistic environment: a project, services, data, documents; never a
    puzzle.
  * HIDDEN EVALUATION: the tests check {MIN_CHECKS} to {MAX_CHECKS} independent CHECKS on inputs the agent never
    sees: held-out data or examples, a load generator, hidden edge cases, inputs drawn from several
    seeds. Each check follows from a sentence of instruction.md, a document it names, or a fact
    visible in the environment; each differs from what a reasonable implementer assumes by default.
    Passing needs all of them; the agent tests what it thinks of.
  * Ground truth never comes from your own reasoning: every expected value is computed by code the
    tests run (a pristine reference kept in tests/, a package installed only for the verifier, or
    the seeded generator that made the data), so a detail you misremember cannot make the solution
    and the tests wrong together. The oracle (solution/solve.sh) must pass every check.
  * Nothing in the environment gives the answer away: no expected outputs, no reference
    implementation, no verify command, no backup or original of the correct code, no .git with the
    fix. The one exception is a reference program that IS the specification (a legacy binary to
    match); the tests then compile or copy their own pristine copy and hide the environment's one.
    Public tests are the one other exception: tests for the COMMON path only (about 30% of what the
    hidden tests cover, e.g. in tests_public/) may ship so the agent's verify loop works; they never
    contain a hidden input or an edge case.
  * Fair: an expert reading instruction.md and the environment can derive every check. Every
    exception to a general rule is named in instruction.md; where two behaviours are both
    reasonable (reject vs sanitise, round before vs after) instruction.md states which is required.
    Existing behaviour must keep working ("everything the tool does today must keep working",
    checked by hidden regression tests). Deterministic and offline: no clocks, randomness or
    network in what the tests check; every package the solution needs is in the image.
  * A SEED CARD, when given with the topic, is binding: keep its shape, build the evaluation
    around its `agent_cannot_verify` mechanism, set the `dial` it names (its fair range and starting
    value), compute ground truth the way it says, include its seed checks among `checks`, use its
    knobs and must_keep, and stay inside its `out_of_bounds`. Draw the hidden instances from its
    `quirk_matrix` in the stated mix (one level per dimension per instance; never only easy cells),
    ship its `public_tests` and nothing more, and enforce its `anti_cheese` gate with a hidden test.
    Its environment notes are limits.
"""

DIFFICULTY_SPEC_FIELDS = """,
  "shape": "the kind of work, in the topic's words (e.g. rule induction from examples, live migration under load)",
  "hidden_evaluation": "what the tests check that the agent cannot fully reproduce, and how (held-out data, load generator, seeds)",
  "checks": [{"requirement": "the instruction.md (or named document) sentence the check follows from",
              "assumed_instead": "what a reasonable implementer would do without reading it carefully",
              "hidden_test_input": "the input or scenario the hidden test uses",
              "why_missed": "why a careful agent's own testing might not cover it"}],
  "preserved_behaviours": [{"behaviour": "an existing behaviour that must keep working", "hidden_test_input": "the input whose output must stay the same"}],
  "ground_truth": "how the tests compute every expected value (reference in tests/, verifier-only package, seeded generator)",
  "dial": "what moves the pass rate, its fair range and the chosen value (from the seed card when given); empty if none",
  "quirk_matrix": "dimensions x levels the hidden instances are drawn from, and the mix (from the seed card)",
  "public_tests": "what the visible common-path tests cover (about 30%), and where they ship",
  "anti_cheese": "the paired gate that stops a shortcut (performance budget, forbidden library or file, output identity) and its hidden test",
  "verifier_packages": ["pip packages the tests need, as name==version (installed only for the verifier); may be empty"],
  "verifier_apt": ["Debian packages the tests need (e.g. gcc to compile a pristine reference); may be empty"],
  "reference_in_environment": "none, or the reference program that IS the specification and how the tests hide it"
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
instruction.md or of the spec document it names (given after instruction.md when there is one),
or the fact visible in the environment, such as the program's existing output words, that
requires what the assertion checks. Test names, docstrings and comments are NOT
requirements: the agent never sees them. If no sentence or derivable consequence of the stated
goal requires what the failing assertion checks, it is "task" (a test checking an unstated
choice), even if every other test passed. Example: the goal is "each event affects the balance
exactly once"; the failing assertion requires the receiver to print "duplicate" for a retry; the
balance was correct; nothing asks for that output -> "task".
Two more rules. A test input that violates the stated property (a CRLF in a header value, a path
with "..") is NOT "legitimate functionality": rejecting it does not break a "keep everything
working" clause. And when two fixes are both valid (reject with an error vs sanitise and answer;
strip vs escape) and instruction.md does not say which, a test that pins one of them is "task"
(ambiguous-spec), even if the other runs happened to pick the tested one. Also "task": a run that
followed one instruction.md sentence and so broke another (a general rule vs a documented
exception the instruction does not name): quote both; the conflict is the task's. Also "task": the
verifier's own server or fixture failing (connection refused or closed on every request,
including requests unrelated to the fix) when the agent's code is otherwise correct.
Reply with ONE JSON object and nothing else:
{"fault": "model" or "task" or "unknown", "category": "short label, e.g. wrong-diagnosis,
 incomplete-fix, gave-up, broke-something, ambiguous-spec, untested-requirement, broken-env",
 "reason": "one sentence, concrete",
 "evidence": ["specific observations from the verifier output or trajectory"],
 "failed_requirements": ["the requirement(s) from instruction.md the run did not meet"],
 "requirement_quote": "for 'model': the exact instruction.md sentence (or environment fact) the failing assertion enforces; empty otherwise"}
"""


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
it reads files, greps, runs builds and tests, writes its own end-to-end tests, and probes any
reference it may run; it solved every task whose correctness it could check by itself.

{DIFFICULTY_RULE}
Given a task spec (JSON), walk through how that agent would solve it: which checks it would get
right on its own, which it would verify with its own tests, and which it would likely miss. The
spec is TOO EASY if it has fewer than {MIN_CHECKS} checks, if the agent could reproduce the hidden
evaluation (all hidden inputs are guessable from the examples, a reference answers every case), if
most checks match what a programmer does by default, if several checks are one check restated, or
if anything in the environment or instruction gives the answer away. It is UNFAIR if a check does
not follow from instruction.md, a named document or the environment, if two reasonable readings
give different results, if an expected value comes from the designer's reasoning instead of code
the tests run, or if anything depends on timing, randomness or the network.

If results of earlier designs are given, a design that repeats a shape those results show was
too easy is too easy. If it is too easy or unfair, rewrite the spec to fix every problem while
keeping it fair, solvable, deterministic and on the same topic.

The revised spec must keep every key of the original AND include these design keys, filled in:
{{{DIFFICULTY_SPEC_FIELDS.lstrip(",")}
}}

Reply with ONE JSON object and nothing else:
{{"walkthrough": ["how the agent would approach the ORIGINAL spec, check by check"],
  "too_easy_because": ["problems found, empty if none"],
  "spec": {{...the full spec, revised if needed, with every key of the original...}}}}
"""


INSTRUCTION_REVIEW_SYSTEM = """\
You review instruction.md of a Terminal-Bench 2 task before it is built. The agent solving the
task sees only instruction.md and the environment (including any document instruction.md names,
given below). Every check the hidden tests make must follow from instruction.md, a named document
or the environment; the hidden INPUTS must stay hidden.

Check, against the list of checks and tests/test_outputs.py given to you:
  1. MISSING RULE: a check the tests make that nothing the agent can see states, or states so
     vaguely that two reasonable readings give different results, or that two passages contradict
     (a general rule and an exception instruction.md does not name).
  2. LEAKED ANSWER: expected output beyond trivial examples, a sample that covers the hidden
     inputs, or a hint of which cases the tests probe.
  3. ORACLE: an instruction to run something whose output signals completion, or a pointer to a
     reference implementation (unless the reference IS the specification the task asks to match).
  4. UNSTATED FORMAT: a test requires an exact textual form no sentence states; report it as
     "UNSTATED FORMAT: <test> requires <form>".
Also make sure the interface is stated: the command or entry point, inputs, outputs, exit codes.
Pattern-scan hints may be given below; they are often false alarms (a rule constant is not a
pasted answer, a file the task must name is not a leak). Act on a hint only if it is a real
problem by the four checks above.

If nothing violates this, reply exactly:
VERDICT: clean

Otherwise reply:
VERDICT: leaks
- <the problem> -> <which check or test it concerns>
<<<FILE instruction.md>>>
...the full rewritten instruction.md...
<<<END>>>

The rewrite keeps the problem statement, adds the missing or sharpened requirements, removes
leaked outputs and oracle pointers, and stays in the same voice. When the problem is in a named
document, return the rewritten document as a second block under its own path (e.g.
<<<FILE environment/docs/STYLE.md>>>). For an UNSTATED FORMAT, add the form only if it is a
genuine part of the requirement; otherwise the test is the problem and must be reported.
"""


def instruction_review_user(instruction: str, checks: list, tests: str, crux: str = "", genre: str = "",
                            docs: dict[str, str] | None = None, hints: list[str] | None = None) -> str:
    doc_text = "".join(f"\n\nDocument {path} (shipped in the environment):\n{body[:12000]}"
                       for path, body in (docs or {}).items())
    return ("Checks the hidden tests make (each must follow from what the agent can see; never reveal their inputs):\n"
            + json.dumps(checks, indent=2)
            + "\n\ntests/test_outputs.py (keep everything these rely on):\n" + tests[:8000]
            + doc_text
            + ("\n\nPattern-scan hints (act only on real problems):\n- " + "\n- ".join(hints) if hints else "")
            + "\n\ninstruction.md to review:\n" + instruction)


MUTANT_SYSTEM = """\
You write deliberately INCOMPLETE solutions for a Terminal-Bench 2 task, to check that its hidden
tests catch a plausible partial solution. You get the task's items (each with `wrong_fix`, the
plausible incomplete behaviour, and a `counterexample`) and the correct solution/solve.sh.

For each item, write a complete alternative solve script that does everything the correct
solve.sh does, EXCEPT that for this one item it does `wrong_fix` instead. Keep every other step
identical, so the only difference is that one item. The script must run without errors (bash,
`set -euo pipefail`) and must not break unrelated things.

Reply with one block per item, nothing before or after, named by the item's index:
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


def critic_user(spec: dict, calibration: str = "", seed: str = "") -> str:
    return ("Task spec to review:\n\n" + json.dumps(spec, indent=2) + "\n"
            + (f"\nThe seed card the design must follow (binding):\n{seed}\n" if seed else "")
            + (f"\nResults of earlier designs under these rules:\n{calibration}\n" if calibration else ""))


BAND_REVIEW_SYSTEM = TRIAGE_SYSTEM.split("Reply with ONE JSON object")[0] + """\
You review ALL runs of one task at once. Give a verdict for every FAILED run (by its trial name)
using the rules above, then the lesson for the designer of the next task: in 2-3 plain sentences,
WHY the task landed where it did (which checks every run got right and how: read, derived, tested
itself; which caused failures) and what the next design should do differently or keep.

Reply with ONE JSON object and nothing else:
{"runs": [{"trial": "trial name", "fault": "model" or "task" or "unknown", "category": "short label",
           "reason": "one sentence", "evidence": ["observations"], "failed_requirements": ["..."],
           "requirement_quote": "for 'model': the exact sentence the failing assertion enforces; empty otherwise"}],
 "lesson": "2-3 sentences", "held": ["checks every run got right"], "failed": ["checks that caused failures"]}
"""


def band_review_user(instruction: str, tests: str, spec: dict, mutation: list, trials: list, failed: list) -> str:
    design = {"name": spec.get("name"), "shape": spec.get("shape"),
              "checks": [str(c.get("requirement"))[:160] for c in spec.get("checks") or [] if isinstance(c, dict)],
              "knobs": [str(k.get("knob"))[:80] for k in spec.get("knobs") or [] if isinstance(k, dict)]}
    runs = [{"trial": t.get("trial"), "outcome": t.get("outcome"), "steps": t.get("episodes"),
             "failed_tests": t.get("failed_tests")} for t in trials]
    detail = "".join(f"\n\n=== failed run {f['trial']} ===\nVerifier output:\n{f['test_output']}\n"
                     f"Last steps of the agent's trajectory:\n{f['trajectory_tail']}" for f in failed)
    return (f"instruction.md:\n{instruction}\n\ntests/test_outputs.py:\n{tests[:8000]}\n\nDesign:\n"
            + json.dumps(design, indent=1) + "\n\nMutation check (incomplete solutions vs the tests):\n"
            + json.dumps([{k: m.get(k) for k in ("fault", "verdict")} for m in mutation or []])
            + "\n\nAll runs:\n" + json.dumps(runs, indent=1) + detail + "\n")


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


FUZZ_RULE = """
Generated-input test (required): besides the fixed tests, tests/ holds a copy of the reference
solution (e.g. tests/reference_tool.py, never shipped in the environment) and a seeded,
deterministic input generator (tests/gen_cases.py, stdlib random with a fixed seed, about 1,000
cases). One test runs the agent's program and the reference on every generated input and fails
on the first differences, printing the input, both outputs and the rule involved. The generator
only produces inputs whose output the stated rules fully determine: leave out combinations the
instruction does not settle (ordering of two steps it does not order, edge cases it does not
name), or settle them in instruction.md first.
"""


DIFFICULTY_KNOBS = """
- DIFFICULTY KNOBS (pick 2 to 4 that suit the topic, list them under `knobs`; each needs its fairness
  condition, or the design is unfair). Careful agents fail on these because doing the work right is
  costly, not because anything is hidden:
  * Drift during the episode: data or a service changes after a stated trigger (the Nth request, a
    record arriving at a stated cutoff). Fair only if instruction.md says the world changes and states
    the final-state rule. Triggers are event-based, never wall-clock.
  * Contradicting sources with a stated precedence (a stale README vs the current procedure vs the live
    schema). Fair only if the precedence rule is written in the environment.
  * Stale local tests: a shipped test suite wrong in 1-2 places (an exception to "no tests in the
    environment"). Fair only if instruction.md says the specification wins over local tests and the
    correct behaviour is stated.
  * Preservation constraints: immutable records, files that must not change, required CLI flags or DOM
    hooks, byte-identical messages, placed away from the edit site; each stated once, each checked by a
    hidden test.
  * Hidden-edge coverage: any visible example or check covers only the common path (an exception to "no
    oracle" for that path only); every hidden edge case is a sentence of the specification.
  * Convention traps (units, 0- vs 1-based indexes, local vs UTC, decimal separators), each documented in
    a data file or README in the environment.
  * Transient service faults: a local service fails a fixed, seeded share of calls (5-30%) or is slow;
    the procedure document states the retry and idempotency policy; faults are deterministic per run.
  * Resource ceilings: a memory or size limit the naive approach exceeds, stated in instruction.md and
    enforced the same way when grading.
  * Irreversible, audited steps: submissions are final and the audit trail is graded, not only the end
    state; instruction.md says so.
  * Noisy convenient source vs a stated authoritative source (OCR text vs the structured record); which
    source wins is stated.
  * Varied hidden draws: the tests generate hidden inputs from several seeds, so a slightly wrong
    solution fails on some draws; the oracle passes every draw.
  Never combine knobs into a trick: each must be discoverable from the environment by a careful expert.
  A design that uses no knob is TOO EASY; a knob without its fairness condition is UNFAIR.
"""

KNOB_FIELD = """,
  "knobs": [{"knob": "one of the difficulty knobs", "where": "where it lives in the task",
             "fairness": "how its fairness condition is met (the sentence or file that states it)"}]
"""


SEED_MARK = "\n\nSEED CARD (binding):\n"


def load_seed(ref: str) -> str:
    """'@seeds/name.yaml' (relative to scripts/) -> the card's topic sentence plus the whole card."""
    import yaml
    from config import ROOT_DIR
    path = ref.lstrip("@").strip()
    if not os.path.isabs(path):
        path = os.path.join(ROOT_DIR, "scripts", path)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    card = yaml.safe_load(text)
    return str(card["topic"]).strip() + SEED_MARK + text


def seed_of(topic: str) -> str:
    """The seed card inside a topic string, or ''."""
    return topic.split(SEED_MARK, 1)[1] if SEED_MARK in topic else ""


def split_topic(line: str) -> tuple[str, str]:
    """One recipe for every topic. '@seeds/name.yaml' loads a seed card (its topic sentence names
    the task, the whole card goes to the design and the critic); a leading [tag] from older topic
    lists is stripped and ignored. Returns (label, topic); the label is kept for compatibility."""
    if line.strip().startswith("@"):
        return "task", load_seed(line.strip())
    m = re.match(r"\s*\[\w+\]\s*(.*)", line, re.S)
    return "task", (m.group(1) if m else line).strip()


def systems_for(genre: str = "", control: bool = False) -> dict:
    """The stage prompts: the design rule plus the difficulty knobs, and the spec fields plus the
    knob field, everywhere they are embedded (spec stage and critic). control=True strips both."""
    rule = DIFFICULTY_RULE + DIFFICULTY_KNOBS
    fields = DIFFICULTY_SPEC_FIELDS.rstrip("\n") + KNOB_FIELD
    out = {k: v.replace(DIFFICULTY_RULE, "" if control else rule).replace(DIFFICULTY_SPEC_FIELDS, "" if control else fields)
           for k, v in SYSTEMS.items()}
    critic = CRITIC_SYSTEM.replace(DIFFICULTY_RULE, rule).replace(DIFFICULTY_SPEC_FIELDS.lstrip(","), fields.lstrip(","))
    out.update(critic=critic, review=INSTRUCTION_REVIEW_SYSTEM, mutants=MUTANT_SYSTEM)
    if FUZZ_TESTS and not control:
        out.update(files=out["files"] + FUZZ_RULE, repair=out["repair"] + FUZZ_RULE)
    return out


def repair_user(spec: dict, files: dict[str, str], error: str) -> str:
    parts = ["Task spec:\n\n" + json.dumps(spec, indent=2), "\nCurrent files:\n"]
    for path in sorted(files):
        parts.append(f"<<<FILE {path}>>>\n{files[path]}<<<END>>>")
    parts.append("\nFailed check output:\n\n" + error)
    parts.append("\nReturn the fixed files.")
    return "\n".join(parts)
