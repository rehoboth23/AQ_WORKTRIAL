"""
Task generator — generates a Harbor (Terminal-Bench 2) task from a topic string.

Flow for one topic:

    topic
     -> [glm-5.1] spec    (JSON design: scenario, hidden state, solution, test plan)
     -> [glm-5.1] files   (instruction.md, environment/*, solution/solve.sh, tests/test_outputs.py)
     -> Python adds task.toml, tests/test.sh and the canary
     -> checks: validator -> oracle (reward 1) -> nop (reward 0)
     -> on failure: [glm-5.1] repair with the error output, up to MAX_REPAIR_ROUNDS

Output:
    output/<task-name>/          the Harbor task (only if every check passed)
    output/_logs/<run-id>/       audit trail: spec, raw replies, check results, summary.json

The reward contract: tests/test.sh writes `1` (pass) or `0` (fail) to
`/logs/verifier/reward.txt`. See harbor/src/harbor/verifier/verifier.py.
"""

import argparse
import hashlib
import json
import os
import posixpath
import re
import shutil
import sys
import time

import toml
from pydantic import BaseModel, Field, field_validator

import difficulty
import prompts
from checks import _read, run_all, run_harbor
from config import (
    CANARY_LINE,
    GEN_REASONING,
    GEN_REASONING_BUDGET,
    INSTRUCTION_REVIEW,
    LOGS_DIR,
    BONUS_REPAIR_ROUND,
    ORACLE_MAX_SEC,
    VERIFY_MAX_SEC,
    MAX_REPAIR_ROUNDS,
    MAX_SPEC_ATTEMPTS,
    MODEL,
    MUTATION_CHECK,
    NEED_TO_KNOW,
    MUTANT_TOLERANCE,
    OUTPUT_DIR,
    SPEC_CRITIC,
    TASK_ORG,
)
import llm
from ledger import reserve_dir, write_text_atomic
from llm import LLMError, parse_file_blocks, parse_json_object


def chat(system: str, user: str, parse, log=None, label: str = "call"):
    """llm.chat with a reply cache in the run's logs dir (README Part 4: resume without
    re-paying). Replies are keyed by model + prompts; a resumed run gets the same prompts for
    every call that finished before the kill, so those replies come back free."""
    # Per-stage reasoning effort (config.GEN_REASONING), by the label's stage name.
    stage = re.split(r"[-_]", label, maxsplit=1)[0]
    effort, budget = GEN_REASONING.get(stage), GEN_REASONING_BUDGET.get(stage) or None
    run = getattr(log, "__self__", None)
    if not isinstance(run, RunLog):
        return llm.chat(system, user, parse, log, label, reasoning=effort, reasoning_budget=budget)
    salt = f"\0{effort}" if effort else ""  # unset effort keeps the earlier cache keys valid
    key = hashlib.sha256(f"{MODEL}\0{system}\0{user}{salt}".encode("utf-8")).hexdigest()[:24]
    path = os.path.join(run.dir, "cache", f"{key}.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        try:
            parsed = parse(text)
        except Exception:  # cached reply no longer parses (parser changed): pay again
            pass
        else:
            run.event("llm_cached", label=label, key=key)
            return parsed, text, {}
    parsed, text, usage = llm.chat(system, user, parse, log, label, reasoning=effort, reasoning_budget=budget)
    write_text_atomic(path, text)
    return parsed, text, usage

CANARY_COMMENT = f"# {CANARY_LINE}"

# Copied from harbor/src/harbor/cli/template-task/pytest-tests/test.sh.
TEST_SH = """\
#!/bin/bash

# Installs the test runner and runs /tests/test_outputs.py; writes the reward.
apt-get update
apt-get install -y curl

curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh

source $HOME/.local/bin/env

uvx \\
  --with pytest==8.4.1 \\
  --with pytest-json-ctrf==0.3.5 \\
  pytest --ctrf /logs/verifier/ctrf.json /tests -rA

if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
"""


class Spec(BaseModel):
    name: str
    description: str
    difficulty: str = "hard"
    category: str = "software-engineering"
    tags: list[str] = Field(default_factory=list)
    expert_time_estimate_min: float = 60.0
    junior_time_estimate_min: float = 180.0
    base_image: str = ""
    scenario: str = ""
    environment_setup: str = ""
    instruction_summary: str = ""
    solution_outline: list[str] | str = ""
    test_plan: list[str] | str = ""
    anti_cheat: str = ""
    failure_modes: str = ""
    # Design fields (prompts.DIFFICULTY_SPEC_FIELDS), checked by difficulty.spec_gate().
    shape: str = ""
    hidden_evaluation: str = ""
    checks: list[dict] = Field(default_factory=list)
    preserved_behaviours: list[dict] = Field(default_factory=list)
    ground_truth: str = ""
    verifier_packages: list[str] = Field(default_factory=list)
    verifier_apt: list[str] = Field(default_factory=list)
    reference_access: str = ""          # none | frozen_examples | runnable: <reason>
    quirk_evidence: list[dict | str] = Field(default_factory=list)
    answer_source: str = ""             # stated | inferred
    inferred_rules: list[dict | str] = Field(default_factory=list)
    stated_facts: list[dict | str] = Field(default_factory=list)
    reference_binary: str = ""          # set when a reference program IS the specification
    sample_file: str = ""
    spec_document: str = ""             # a document instruction.md names as the specification
    knobs: list[dict] = Field(default_factory=list)
    dial: str = ""                      # what moves the pass rate (from the seed card)
    quirk_matrix: str = ""              # dimensions x levels the hidden instances are drawn from
    public_tests: str = ""
    anti_cheese: str = ""
    graded_instances: str = ""
    self_check_gap: str = ""
    margins: list[dict | str] = Field(default_factory=list)
    contract: list[str] | str = Field(default_factory=list)
    invisible_traps: list[dict | str] = Field(default_factory=list)
    instance_plan: list[dict | str] = Field(default_factory=list)
    adjust_rules: dict | str = Field(default_factory=dict)
    seed_card: str = ""                 # the binding seed card (attached after design; read by every later stage)
    crux: str = ""
    expected_agent_steps: float | None = None

    @field_validator("description", "scenario", "environment_setup", "instruction_summary", "anti_cheat",
                     "failure_modes", "crux", "shape", "hidden_evaluation", "ground_truth", "reference_access", "answer_source", "dial",
                     "quirk_matrix", "public_tests", "anti_cheese", "graded_instances", "self_check_gap",
                     "base_image", "category",
                     mode="before")
    @classmethod
    def _text(cls, v):
        """glm-5.1 sometimes returns bullet lists for prose fields; join them instead of
        rejecting a whole (6-minute) reply."""
        if isinstance(v, list):
            return "\n".join(f"- {x}" if not isinstance(x, (dict, list)) else f"- {json.dumps(x)}" for x in v)
        if isinstance(v, dict):
            return json.dumps(v)
        return v

    @field_validator("tags", "verifier_packages", "verifier_apt", mode="before")
    @classmethod
    def _str_list(cls, v):
        if isinstance(v, str):
            return [v]
        return [x if isinstance(x, str) else json.dumps(x) for x in (v or [])]

    @field_validator("expected_agent_steps", mode="before")
    @classmethod
    def _steps(cls, v):
        if isinstance(v, str):  # e.g. "15-25" -> 15
            import re as _re
            m = _re.search(r"\d+(\.\d+)?", v)
            return float(m.group()) if m else None
        if isinstance(v, list):  # the model enumerated the steps instead of counting them (a 9-minute critic reply was lost to this)
            return float(len(v)) if v else None
        if isinstance(v, dict):
            return None
        return v


def slugify(text: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "task"


def parse_spec(text: str) -> dict:
    spec = Spec.model_validate(parse_json_object(text)).model_dump()
    spec["name"] = slugify(spec["name"], 40)
    if spec["difficulty"] not in ("easy", "medium", "hard"):
        spec["difficulty"] = "hard"
    return spec


def parse_critic(text: str) -> dict:
    obj = parse_json_object(text)
    if not isinstance(obj.get("spec"), dict) and "checks" in obj and "name" in obj:
        # glm-5.1 sometimes writes the walkthrough as prose and returns the revised spec bare;
        # keep it rather than throw away a 40k-token reply.
        obj = {"walkthrough": [text[:text.find("{")].strip()[:4000]], "too_easy_because": [], "spec": obj}
    if not isinstance(obj.get("spec"), dict):
        raise ValueError("critic reply has no `spec` object")
    return {"too_easy_because": obj.get("too_easy_because") or [],
            "walkthrough": obj.get("walkthrough") or [],
            "spec": parse_spec(json.dumps(obj["spec"]))}


class SpecRejected(Exception):
    """The design still fails the difficulty spec gate after every attempt."""


def design_spec(topic: str, calibration: str, control: bool, systems: dict, log, genre: str = "spec") -> dict:
    """Spec call(s), then the difficulty gate and the red-team critic (both skipped for control).
    Raises SpecRejected if no design passes the gate, before any files or Docker are spent."""
    user = prompts.spec_user(topic, calibration)
    for attempt in range(MAX_SPEC_ATTEMPTS):
        spec, _, _ = chat(systems["spec"], user, parse_spec, log.llm, "spec" if attempt == 0 else f"spec-a{attempt}")
        if control:
            return spec
        spec = seed_fill(spec, prompts.seed_of(topic))
        problems = difficulty.spec_gate(spec, genre) + difficulty.seed_gate(spec, prompts.seed_of(topic))
        log.event("spec_gate", attempt=attempt, problems=problems)
        if not problems:
            break
        user = prompts.spec_retry_user(topic, calibration, problems)

    if SPEC_CRITIC:
        try:
            critic, _, _ = chat(systems["critic"], prompts.critic_user(spec, calibration, prompts.seed_of(topic)),
                                parse_critic, log.llm, "critic")
            log.write_json("critic.json", critic)
            critic["spec"] = seed_fill(critic["spec"], prompts.seed_of(topic))
            revised_problems = difficulty.spec_gate(critic["spec"], genre) + difficulty.seed_gate(critic["spec"], prompts.seed_of(topic))
            log.event("critic", too_easy_because=critic["too_easy_because"], revised_gate=revised_problems)
            if not revised_problems:
                spec = critic["spec"]
        except LLMError as e:  # the critic is an improvement step; keep the gated spec without it
            log.event("critic_error", error=str(e)[:300])

    seed = prompts.seed_of(topic)
    problems = difficulty.spec_gate(spec, genre) + difficulty.seed_gate(spec, seed)
    if problems:
        raise SpecRejected("spec failed the difficulty gate: " + "; ".join(problems))
    if seed:
        spec = {**spec, "seed_card": seed}  # project, files, repair and review stages read it from the design
    return spec


def parse_review(text: str) -> dict:
    """Instruction-review reply: 'VERDICT: clean', or 'VERDICT: leaks' + leak lines + a file block."""
    m = re.search(r"VERDICT:\s*(clean|leaks)", text, re.I)
    if not m:
        raise ValueError("no VERDICT line in review reply")
    if m.group(1).lower() == "clean":
        return {"verdict": "clean", "leaks": [], "instruction": None}
    blocks = parse_file_blocks(text)  # raises ValueError if the rewrite is missing
    if "instruction.md" not in blocks and not any(p.startswith("environment/") for p in blocks):
        raise ValueError("leaks reported but no rewritten instruction.md or spec document")
    head = text[m.end(): text.find("<<<FILE")]
    leaks = [l.strip("- ").strip() for l in head.splitlines() if l.strip().startswith("-")]
    return {"verdict": "leaks", "leaks": leaks, "instruction": blocks.get("instruction.md"),
            "docs": {p: b for p, b in blocks.items() if p.startswith("environment/")}}


def review_instruction(spec: dict, files: dict[str, str], log, systems: dict | None = None, genre: str = "spec",
                       hints: list[str] | None = None) -> dict[str, str]:
    """Rewrite instruction.md if it diagnoses a hidden fault (keeps requirements). Best effort:
    on a model error the instruction is kept and the gates and band eval still apply."""
    docs = difficulty.spec_docs(files, spec)
    # Every other shipped document too: the agent reads them whether or not instruction.md names
    # them (an unnamed data/README.md once listed every rule of an inferred task, and its order).
    others = [(p, b) for p, b in sorted(files.items()) if p.startswith("environment/") and p not in docs
              and p.lower().endswith(difficulty._SPEC_DOC_EXTS) and len(b) <= 20000]
    docs = {**docs, **dict(others[:10])}
    try:
        review, _, _ = chat((systems or {}).get("review") or prompts.INSTRUCTION_REVIEW_SYSTEM,
                            prompts.instruction_review_user(files["instruction.md"], mutation_items(spec),
                                                            files.get("tests/test_outputs.py", ""),
                                                            spec.get("crux", ""), genre, docs, hints),
                            parse_review, log.llm, "review")
    except LLMError as e:
        log.event("review_error", error=str(e)[:300])
        return files
    log.event("instruction_review", verdict=review["verdict"], leaks=review["leaks"])
    if review["instruction"]:
        files = {**files, "instruction.md": review["instruction"]}
    for path, body in (review.get("docs") or {}).items():
        if path in docs:  # only shipped documents may be rewritten here, never the code
            files = {**files, path: body}
    return files


def mutation_items(spec: dict) -> list[dict]:
    """What the mutation check tries one at a time: a check done the way a reasonable implementer
    would assume, a preserved behaviour dropped, a difficulty knob ignored. The hidden tests must
    fail each one."""
    items = []
    for i, c in enumerate(spec.get("checks") or []):
        if isinstance(c, dict) and str(c.get("requirement") or "").strip():
            items.append({"where": f"check {i}", "what": "requirement: " + str(c.get("requirement")),
                          "wrong_fix": "do what a reasonable implementer would assume instead: " + str(c.get("assumed_instead") or ""),
                          "counterexample": c.get("hidden_test_input"), "caught_by_test": f"check {i}",
                          "caught_by_tests": [str(t).rsplit("::", 1)[-1] for t in c.get("caught_by_tests") or []]})
    for i, p in enumerate(spec.get("preserved_behaviours") or []):
        if isinstance(p, dict) and str(p.get("behaviour") or "").strip():
            items.append({"where": f"preserved {i}", "what": "existing behaviour: " + str(p.get("behaviour")),
                          "wrong_fix": "a solution that drops this existing behaviour (e.g. a rewrite from the requirements alone)",
                          "counterexample": p.get("hidden_test_input"), "caught_by_test": f"preserved {i}"})
    for i, k in enumerate(spec.get("knobs") or []):
        if isinstance(k, dict) and str(k.get("knob") or "").strip():
            items.append({"where": k.get("where"), "what": f"knob {i}: {k.get('knob')}",
                          "wrong_fix": "a solution that ignores this difficulty knob: " + str(k.get("knob")),
                          "counterexample": k.get("fairness"), "caught_by_test": f"knob {i}"})
    return items


def _ctrf_failed(trial_dir: str | None) -> list[str]:
    """Names of the tests a mutant run failed (from the verifier's CTRF report)."""
    try:
        with open(os.path.join(trial_dir or "", "verifier", "ctrf.json"), encoding="utf-8") as f:
            tests = json.load(f)["results"]["tests"]
    except (OSError, KeyError, TypeError, ValueError):
        return []
    return [t.get("name", "?").rsplit("::", 1)[-1] for t in tests if t.get("status") not in ("passed", "skipped")]


def mutation_check(task_dir: str, spec: dict, files: dict[str, str], log, job_prefix: str, mutant_system: str | None = None) -> dict:
    """Run each fault's `wrong_fix` as a mutant solve.sh in a copy of the task; the tests must
    fail it. A mutant the tests pass means that trap is not real. A mutant that fails EVERY test
    probably broke something unrelated, so it proves nothing either way ("broken")."""
    faults = mutation_items(spec)
    if not faults:
        return {"survived": [], "results": []}
    try:
        blocks, _, _ = chat(mutant_system or prompts.MUTANT_SYSTEM, prompts.mutants_user(faults, files["solution/solve.sh"]),
                            parse_file_blocks, log.llm, "mutants")
    except LLMError as e:
        log.event("mutation_error", error=str(e)[:300])
        return {"survived": [], "results": [], "error": str(e)[:300]}
    results = []
    claimed = {n for f in faults for n in (f.get("caught_by_tests") or [])}
    for path in sorted(blocks):
        m = re.fullmatch(r"mutants/(\d+)\.sh", path.strip())
        if not m or int(m.group(1)) >= len(faults):
            continue
        idx = int(m.group(1))
        mdir = os.path.join(log.dir, "mutants", f"{idx}-{time.strftime('%H%M%S')}")
        shutil.copytree(task_dir, mdir)
        with open(os.path.join(mdir, "solution", "solve.sh"), "w", encoding="utf-8") as f:
            f.write(_with_canary(blocks[path]))
        r = run_harbor(mdir, "oracle", f"{job_prefix}-mutant{idx}")
        failed, total = _ctrf_counts(r.details.get("trial_dir"))
        failed_names = _ctrf_failed(r.details.get("trial_dir"))
        verdict = ("survived" if r.reward == 1.0 else "broken" if total and failed == total
                   else "killed" if r.reward is not None else "error")
        result = {"fault": idx, "wrong_fix": faults[idx].get("wrong_fix"), "verdict": verdict,
                  "failed_tests": failed, "total_tests": total, "job_dir": r.job_dir, "failed_names": failed_names}
        named = faults[idx].get("caught_by_tests") or []
        base = {re.sub(r"\[.*\]$", "", n) for n in failed_names}
        # A test no check claims was added for a case after the design (a repair cannot edit the
        # check's list): it is dedicated, so it counts. A test another check claims does not.
        if verdict == "killed" and named and not set(named) & base and not base - claimed:
            # Caught, but not by the tests that are meant to check this behaviour: the named tests miss it.
            verdict = result["verdict"] = "caught_elsewhere"
            result["named_tests"] = named
        if verdict == "survived":  # a gap in the tests, or a partial fix that is in fact correct?
            eq = _equivalence(faults[idx], files, blocks[path], log, idx)
            result.update(eq)
            if eq.get("equivalent"):
                result["verdict"] = "equivalent"
        results.append(result)
        shutil.rmtree(mdir, ignore_errors=True)
    log.event("mutation_check", results=[{k: v for k, v in x.items() if k != "job_dir"} for x in results])
    return {"survived": [x for x in results if x["verdict"] in ("survived", "caught_elsewhere")], "results": results}


def _parse_equivalence(text: str) -> dict:
    obj = parse_json_object(text)
    if not isinstance(obj.get("equivalent"), bool):
        raise ValueError("`equivalent` must be true or false")
    return {"equivalent": obj["equivalent"], "distinguishing_case": str(obj.get("distinguishing_case") or ""),
            "equivalence_reason": str(obj.get("reason") or "")}


def _equivalence(fault: dict, files: dict[str, str], mutant_sh: str, log, idx: int) -> dict:
    """Ask whether a surviving mutant is behaviourally equivalent to the full fix (then the fault is
    redundant and no test can fail it) or there is a case the tests miss (returned as a test recipe).
    On a model error the mutant counts as survived, as before."""
    try:
        eq, _, _ = chat(prompts.EQUIVALENCE_SYSTEM,
                        prompts.equivalence_user(fault, files.get("instruction.md", ""), files["solution/solve.sh"], mutant_sh),
                        _parse_equivalence, log.llm, f"mutants-equiv{idx}")
        return eq
    except LLMError as e:
        return {"equivalent": False, "distinguishing_case": "", "equivalence_reason": f"check failed: {e}"[:200]}


def _ctrf_counts(trial_dir: str | None) -> tuple[int, int]:
    """(failed, total) tests of a trial, from the verifier's CTRF report."""
    try:
        tests = json.loads(_read(os.path.join(trial_dir or "", "verifier", "ctrf.json")) or "{}")["results"]["tests"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return 0, 0
    return sum(t.get("status") not in ("passed", "skipped") for t in tests), len(tests)


def clean_files(raw: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Keep only paths the model may write; strip any canary lines it added."""
    kept, dropped = {}, []
    for path, body in raw.items():
        norm = posixpath.normpath(path.strip().lstrip("./"))
        allowed = norm in prompts.MODEL_FILES or (
            norm.startswith(prompts.MODEL_DIRS) and ".." not in norm.split("/")
        )
        if not allowed or norm.startswith("/"):
            dropped.append(path)
            continue
        kept[norm] = "".join(l for l in body.splitlines(keepends=True) if "terminal-bench-canary" not in l)
    return kept, dropped


def missing_files(files: dict[str, str]) -> list[str]:
    return [p for p in prompts.MODEL_FILES if not files.get(p, "").strip()]


_HEREDOC = re.compile(r"python3?\s+-\s*<<\s*['\"]?(\w+)['\"]?\n(.*?)\n\1\b", re.S)


def syntax_errors(files: dict[str, str]) -> list[str]:
    """Python that was written but never run: compile every .py file and every Python heredoc in
    solve.sh before any Docker spend. A test file with an IndentationError collects nothing, so the
    oracle fails after a full build and an agent run (key rotation lost a 10-minute round to one)."""
    out = []
    for path, body in sorted(files.items()):
        if path.endswith(".py"):
            try:
                compile(body, path, "exec")
            except SyntaxError as e:
                out.append(f"{path}: {e.msg} at line {e.lineno}")
    for m in _HEREDOC.finditer(files.get("solution/solve.sh", "")):
        try:
            compile(m.group(2), "solution/solve.sh (python heredoc)", "exec")
        except SyntaxError as e:
            out.append(f"solution/solve.sh python heredoc: {e.msg} at line {e.lineno}")
    return out


def missing_copy_sources(files: dict[str, str]) -> list[str]:
    """Paths the Dockerfile COPYs/ADDs from the build context that were never written."""
    import fnmatch
    missing = []
    for line in files.get("environment/Dockerfile", "").splitlines():
        m = re.match(r"\s*(COPY|ADD)\s+(.*)", line, re.I)
        if not m or "--from" in m.group(2):
            continue
        args = m.group(2).strip()
        if args.startswith("["):  # JSON form: COPY ["src", "dest"]
            try:
                parts = json.loads(args)
            except json.JSONDecodeError:
                continue
        else:
            parts = [a for a in args.split() if not a.startswith("--")]
        for src in parts[:-1]:
            if src.startswith(("http://", "https://")):
                continue
            src = src.lstrip("./").rstrip("/")
            if src in ("", "."):  # the whole build context: nothing specific to check
                continue
            path = "environment/" + src
            if not any(k == path or k.startswith(path + "/") or fnmatch.fnmatch(k, path) for k in files):
                missing.append(src)
    return missing


def parse_project(text: str) -> dict:
    """Project reply: a <<<MANIFEST>>> of planned paths, then complete file blocks."""
    m = re.search(r"<<<MANIFEST>>>\n(.*?)<<<END>>>", text, re.S)
    manifest = [l.strip() for l in m.group(1).splitlines() if l.strip()] if m else []
    files = parse_file_blocks(text)  # raises ValueError if there are no file blocks at all
    return {"manifest": [p for p in manifest if p.startswith("environment/") and p != "environment/Dockerfile"],
            "files": files}


# Card fields the pipeline copies into the design verbatim (the model is told not to restate them).
SEED_VERBATIM = ("dial", "quirk_matrix", "quirk_evidence", "public_tests", "anti_cheese", "reference_access",
                 "answer_source", "self_check_gap", "knobs", "ground_truth", "stated_facts", "shape")
# Fields the document writer may see; everything else in the design is hidden from it.
PUBLIC_FIELDS = ("name", "description", "scenario", "shape", "environment_setup", "contract", "stated_facts",
                 "public_tests", "verifier_packages", "verifier_apt")
TAMPER_SENTENCE = ("Do not modify the Python interpreter, its standard library or import hooks, or anything "
                   "under /tests; such changes fail the task.")
_DOC_EXT = (".md", ".txt", ".rst", ".adoc")


def _card(seed: str) -> dict:
    try:
        import yaml
        c = yaml.safe_load(seed) if seed else None
        return c if isinstance(c, dict) else {}
    except Exception:
        return {}


def _as_text(v) -> str:
    if isinstance(v, str):
        return v
    import yaml
    return yaml.safe_dump(v, sort_keys=False, allow_unicode=True, width=100).strip()


def seed_fill(spec: dict, seed: str) -> dict:
    """Copy the card's own fields into any the design left empty, verbatim: shorter spec replies, no
    paraphrase drift, and the card's words reach every later stage."""
    card = _card(seed)
    if not card:
        return spec
    out = dict(spec)
    for key in SEED_VERBATIM:
        if key not in card or card[key] in (None, "", [], {}):
            continue
        cur = out.get(key)
        if cur in (None, "", [], {}):
            v = card[key]
            if key in ("knobs", "quirk_evidence", "stated_facts"):
                out[key] = v if isinstance(v, list) else [v]
            else:
                out[key] = _as_text(v)
    return out


def public_design(spec: dict) -> dict:
    """What the document writer may know: the public side only. No checks, hidden inputs, quirks,
    inferred rules, traps, self-check gap, graded instances or seed card."""
    pub = {k: spec.get(k) for k in PUBLIC_FIELDS if spec.get(k) not in (None, "", [], {})}
    dial = str(spec.get("dial") or "")
    if dial:  # the acceptance bar must be stated; the card's baseline figures must not
        pub["acceptance_criterion"] = re.split(r"[.;]\s", dial)[0]
    card = _card(spec.get("seed_card", ""))
    if card.get("must_keep"):
        pub["must_keep"] = card["must_keep"]
    if card.get("environment"):
        pub["environment"] = card["environment"]
    pub["tamper_sentence"] = TAMPER_SENTENCE
    return pub


def _is_doc(path: str) -> bool:
    return path.startswith("environment/") and path.lower().endswith(_DOC_EXT)


def write_docs(spec: dict, project: dict[str, str], doc_paths: list[str], systems: dict, log) -> dict[str, str]:
    """Need-to-know writing: instruction.md and every shipped document from the public design only."""
    paths = ["instruction.md"] + [p for p in doc_paths if p != "instruction.md"]
    docs, _, _ = chat(systems["docs"], prompts.docs_user(public_design(spec), paths, sorted(project)),
                      parse_file_blocks, log.llm, "docs")
    return {p: b for p, b in docs.items() if p == "instruction.md" or _is_doc(p)}


def write_project(spec: dict, systems: dict, log, max_continuations: int = 2) -> dict[str, str]:
    """Write the environment project first (manifest + files), asking for any manifest files a
    cut-off reply left out, so no single reply has to hold the whole task."""
    project, _, _ = chat(systems["project"], prompts.project_user(spec), parse_project, log.llm, "project")
    files, manifest = dict(project["files"]), project["manifest"]
    if NEED_TO_KNOW:  # documents come from the docs writer; drop any the project writer produced anyway
        files = {p: b for p, b in files.items() if not _is_doc(p)}
        files["__docs__"] = "\n".join(p for p in manifest if _is_doc(p))
    for k in range(max_continuations):
        missing = [p for p in manifest if p not in files and not (NEED_TO_KNOW and _is_doc(p))]
        if not missing:
            break
        log.event("project_missing", missing=missing)
        more, _, _ = chat(systems["project"], prompts.project_continue_user(spec, sorted(files), missing),
                          parse_file_blocks, log.llm, f"project-cont{k + 1}")
        files.update(more)
    return files


def _with_canary(body: str) -> str:
    """Put the canary comment at the top, after a shebang or Dockerfile parser directive."""
    lines = body.splitlines(keepends=True)
    head = 0
    while head < len(lines) and (
        lines[head].startswith("#!") or re.match(r"#\s*(syntax|escape|check)\s*=", lines[head])
    ):
        head += 1
    return "".join(lines[:head] + [CANARY_COMMENT + "\n"] + lines[head:])


def task_toml(spec: dict, task_name: str) -> str:
    return toml.dumps({
        "schema_version": "1.1",
        "task": {
            "name": f"{TASK_ORG}/{task_name}",
            "description": spec["description"],
            "keywords": spec["tags"],
        },
        "metadata": {
            "difficulty": spec["difficulty"],
            "category": spec["category"],
            "tags": spec["tags"],
            "expert_time_estimate_min": float(spec["expert_time_estimate_min"]),
            "junior_time_estimate_min": float(spec["junior_time_estimate_min"]),
            "generator_model": MODEL,
        },
        "verifier": {"timeout_sec": 900.0},
        # No network while solving, so the agent can't fetch the original code (the one fair
        # failure we have seen came from removing reference copies). The verifier keeps network.
        "agent": {"timeout_sec": 3600.0, "network_mode": "no-network"},
        "environment": {
            "build_timeout_sec": 600.0,
            "cpus": 1,
            "memory_mb": 2048,
            "storage_mb": 10240,
        },
    })


RUNNER_PACKAGES = {"pytest", "pytest-json-ctrf"}


def test_sh(spec: dict) -> str:
    """TEST_SH plus what the tests need that the agent's image must not have: pinned pip packages
    (a reference library) and Debian packages (e.g. gcc to compile a pristine reference)."""
    # The runner pins pytest and pytest-json-ctrf itself; a design that pins them again (pytest==8.3.4)
    # made uvx unsatisfiable, so every test errored and no repair could fix it (Python writes test.sh).
    pkgs = [str(p).strip() for p in spec.get("verifier_packages") or []
            if difficulty.VERIFIER_PACKAGE.fullmatch(str(p).strip())
            and re.split(r"[=<>!~\[ ]", str(p).strip())[0].lower().replace("_", "-") not in RUNNER_PACKAGES]
    extra = "".join(f"  --with {p} \\\n" for p in pkgs)
    sh = TEST_SH.replace("  --with pytest-json-ctrf==0.3.5 \\\n", "  --with pytest-json-ctrf==0.3.5 \\\n" + extra)
    apt = [str(p).strip() for p in spec.get("verifier_apt") or [] if difficulty._APT_NAME.fullmatch(str(p).strip())]
    if apt:
        sh = sh.replace("apt-get install -y curl", "apt-get install -y curl " + " ".join(apt))
    return sh


GUARD_TEST = '''"""Environment tamper guard, written by the pipeline (never by the task author). Harbor grades in
the agent's own container, so an import hook, a stdlib edit or a swapped interpreter planted during
the agent's turn would survive into grading. Checks the IMAGE interpreter (not the one running
pytest) for anything of that kind changed after the container started."""
import os
import shutil
import subprocess

CHECK = r"""
import glob, os, sys, site, sysconfig
def container_start():
    # Process 1's start time: boot time plus its start ticks. (/proc/1's own timestamps are set
    # when its inode is first looked up, which may be by this very check.)
    try:
        with open("/proc/stat") as f:
            btime = next(int(l.split()[1]) for l in f if l.startswith("btime "))
        with open("/proc/1/stat") as f:
            s = f.read()
        ticks = int(s[s.rindex(")") + 2:].split()[19])  # field 22, counted after the comm field
        return btime + ticks / os.sysconf("SC_CLK_TCK")
    except Exception:
        return os.stat("/proc/1").st_mtime
start = container_start()
def new(p):
    # ctime, not mtime: `touch -t` backdates mtime; nothing short of a clock change backdates ctime.
    try: return os.stat(p).st_ctime > start
    except OSError: return False
bad = []
for name in ("sitecustomize.py", "usercustomize.py"):
    for d in sys.path:
        p = os.path.join(d or ".", name)
        if os.path.exists(p) and new(p): bad.append(p)
dirs = set(site.getsitepackages() + [site.getusersitepackages()])
for d in dirs:
    bad += [p for p in glob.glob(os.path.join(d, "*.pth")) if new(p)]
stdlib = sysconfig.get_paths()["stdlib"]
for root, ds, fs in os.walk(stdlib):
    ds[:] = [x for x in ds if x not in ("site-packages", "dist-packages", "__pycache__")]
    bad += [os.path.join(root, f) for f in fs if f.endswith(".py") and new(os.path.join(root, f))]
# The interpreter as found on PATH (a shim that execs the real binary) and the real binary.
exes = {sys.executable, os.path.realpath(sys.executable)} | set(sys.argv[1:]) | {os.path.realpath(a) for a in sys.argv[1:]}
bad += [e for e in sorted(exes) if e and new(e)]
print("\\n".join(bad))
"""


def test_environment_untampered():
    py = shutil.which("python3", path="/usr/local/bin:/usr/bin:/bin")
    if not py:
        return  # no Python in the image: nothing to hook
    out = subprocess.run([py, "-I", "-c", CHECK, py], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, f"guard could not run: {out.stderr[-500:]}"
    bad = [l for l in out.stdout.splitlines() if l.strip()]
    assert not bad, "environment modified during the agent's turn (import hooks, stdlib or interpreter): " + ", ".join(bad[:8])
'''


def write_task(task_dir: str, spec: dict, task_name: str, files: dict[str, str]) -> None:
    """(Re)write the whole task directory from the model's files plus our boilerplate."""
    # Empty the dir but keep it: removing it would free the reserved name for a moment, and
    # another copy of the pipeline could reserve it in between (found by the concurrency test).
    if os.path.isdir(task_dir):
        for name in os.listdir(task_dir):
            path = os.path.join(task_dir, name)
            shutil.rmtree(path) if os.path.isdir(path) and not os.path.islink(path) else os.remove(path)
    out = dict(files)
    for path in ("environment/Dockerfile", "solution/solve.sh", "tests/test_outputs.py"):
        out[path] = _with_canary(out[path])
    out["tests/test_guard.py"] = _with_canary(GUARD_TEST)  # pipeline-written: the model never sees or edits it
    out["tests/test.sh"] = test_sh(spec)
    out["task.toml"] = task_toml(spec, task_name)
    for rel, body in out.items():
        dest = os.path.join(task_dir, *rel.split("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(body)
        if rel.endswith(".sh"):
            os.chmod(dest, 0o755)


class RunLog:
    """Append-only audit trail for one generation run."""

    def __init__(self, path: str):
        self.dir = path
        os.makedirs(path, exist_ok=True)
        # A resumed run appends to the same dir: continue the NN- numbering, never overwrite.
        self.n = sum(1 for n in os.listdir(path) if re.match(r"\d\d+-", n))
        self.tokens = {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}

    def event(self, kind: str, **data) -> None:
        rec = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": kind, **data}
        with open(os.path.join(self.dir, "events.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    def llm(self, label: str, record: dict) -> None:
        if record.get("phase") == "start":  # call in flight (for live status), no reply yet
            self.event("llm_start", label=label, attempt=record.get("attempt"), model=record.get("model"))
            return
        while True:  # the batch log is shared by every copy: claim a number no other process holds
            self.n += 1
            try:
                with open(os.path.join(self.dir, f"{self.n:02d}-{label}.txt"), "x", encoding="utf-8") as f:
                    f.write(record.get("raw", ""))
                break
            except FileExistsError:
                continue
        for k in self.tokens:  # cost_usd only when the gateway reports it
            self.tokens[k] += (record.get("usage") or {}).get(k) or 0
        self.event("llm_call", label=label, **{k: v for k, v in record.items() if k != "raw"})

    def write_json(self, name: str, data) -> None:
        with open(os.path.join(self.dir, name), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def generate_task(topic: str, output_dir: str | None = None, calibration: str = "",
                  control: bool = False, resume_dir: str | None = None, on_start=None, genre: str = "spec") -> dict:
    """Generate a Harbor task for the given topic.

    Args:
        topic: A short description of the task to generate
            (e.g. "fix a memory bug in a C ring buffer").
        output_dir: Where to write the generated task files.
            Defaults to output/<task-name from the spec>.
        calibration: Optional text with recent band-eval verdicts, appended
            to the spec prompt (see prompts.calibration_block).
        control: Use prompts.CONTROL_SYSTEMS (no difficulty rule) for an
            A/B control arm.
        resume_dir: logs dir of an earlier, killed run of this topic. Its cached
            replies are reused, so finished model calls are not paid again.
        on_start: called with the logs dir as soon as it exists (the batch
            ledger records it, so a kill after this point can resume).

    Returns:
        dict with at least {"task_dir": <path>, "status": "ok" | "failed"}.
    """
    started = time.time()
    if resume_dir:
        run_id = os.path.basename(resume_dir.rstrip("/"))
    else:  # the random suffix keeps two copies started in the same second apart
        run_id = f"{slugify(topic, 40)}-{time.strftime('%Y%m%d-%H%M%S')}-{os.urandom(2).hex()}"
    log = RunLog(resume_dir or os.path.join(os.path.abspath(LOGS_DIR), run_id))
    if on_start:
        on_start(log.dir)
    systems = prompts.systems_for(genre, control)
    log.event("resume" if resume_dir else "start", topic=topic, model=MODEL, calibration=calibration,
              control=control, pid=os.getpid(), genre=genre)
    summary = {"topic": topic, "run_id": run_id, "logs_dir": log.dir, "task_dir": None,
               "status": "failed", "rounds": []}

    def finish(status: str, **extra) -> dict:
        summary.update(status=status, tokens=log.tokens, seconds=round(time.time() - started, 1), **extra)
        log.event("finish", status=status)
        log.write_json("summary.json", summary)
        return summary

    try:
        spec = design_spec(topic, calibration, control, systems, log, genre)
        log.write_json("spec.json", spec)
        project = write_project(spec, systems, log)
        doc_paths = [p for p in project.pop("__docs__", "").split("\n") if p]
        docs = write_docs(spec, project, doc_paths, systems, log) if NEED_TO_KNOW else {}
        core, _, _ = chat(systems["files"], prompts.files_user(spec, project), parse_file_blocks, log.llm, "files")
        if NEED_TO_KNOW:  # the docs writer's versions win: the core writer saw the hidden checks
            core = {p: b for p, b in core.items() if p != "instruction.md" and not _is_doc(p)}
        raw = {**project, **docs, **core}
    except (LLMError, SpecRejected) as e:
        return finish("failed", error=str(e))

    task_name = spec["name"]
    if output_dir:
        task_dir = os.path.abspath(output_dir)
    else:
        # Reserve output/<name> atomically (never overwrite an earlier task, never race another
        # copy of the pipeline); a resumed run reuses the dir it reserved before the kill.
        reserved = os.path.join(log.dir, "task_dir.txt")
        task_dir = (_read(reserved) or "").strip()
        if not (task_dir and os.path.isdir(task_dir)):
            task_dir = reserve_dir(os.path.abspath(os.path.join(OUTPUT_DIR, task_name)))
            write_text_atomic(reserved, task_dir)
        task_name = os.path.basename(task_dir)
    files, dropped = clean_files(raw)

    reviewed = None  # instruction.md text the reviewer last saw
    last_round, bonus_used, rnd = MAX_REPAIR_ROUNDS, False, -1
    while rnd < last_round:
        rnd += 1
        mutation_only = False  # the task passes oracle/nop; only a trap is unguarded by the tests
        record = {"round": rnd, "dropped_paths": dropped, "checks": []}
        if (INSTRUCTION_REVIEW and not control and files.get("instruction.md", "").strip()
                and files["instruction.md"] != reviewed):
            hints = difficulty.files_warnings(files, spec)
            record["warnings"] = hints
            files = review_instruction(spec, files, log, systems, genre, hints)
            reviewed = files["instruction.md"]
        missing = missing_files(files) + [f"environment/{p} (the Dockerfile COPYs it, but it was never written)"
                                          for p in missing_copy_sources(files)]
        missing += [f"{s} (Python that does not compile; fix the syntax)" for s in syntax_errors(files)]
        leaks = difficulty.meta_leaks(files)  # both arms: the agent must never see the design
        if leaks:
            missing += ["spec details visible to the solving agent (remove them, make the code look "
                        "ordinary): " + "; ".join(leaks[:8])]
        gate = [] if control or missing else difficulty.files_gate(files, spec)
        record["difficulty_gate"] = gate
        if missing:
            error = "These required files are missing or empty: " + ", ".join(missing)
        elif gate:  # too easy by construction: fix it before spending on Docker
            error = ("The task is too easy by construction (difficulty gate). Fix all of these:\n- "
                     + "\n- ".join(gate))
        else:
            write_task(task_dir, spec, task_name, files)
            # Time-stamped so a resumed run never reuses a job dir a killed run left behind.
            results = run_all(task_dir, f"gen-{run_id}-r{rnd}-{time.strftime('%H%M%S')}")
            record["checks"] = [r.to_dict() for r in results]
            error = next((r.error for r in results if not r.passed), "")
            oracle = next((r for r in results if r.name == "oracle" and r.passed), None)
            if not error and oracle:
                a, v = oracle.details.get("agent_sec"), oracle.details.get("verifier_sec")
                record["oracle_seconds"] = {"solve": a, "verify": v}
                if (a or 0) > ORACLE_MAX_SEC or (v or 0) > VERIFY_MAX_SEC:
                    error = (f"Time budget: the oracle solve took {a}s (budget {ORACLE_MAX_SEC:.0f}s) and the tests took "
                             f"{v}s (budget {VERIFY_MAX_SEC:.0f}s). Make the solution and the hidden checks faster "
                             "(fewer or smaller graded instances, no repeated builds) without weakening any check.")
            if not error and MUTATION_CHECK and not control:
                mut = mutation_check(task_dir, spec, files, log, f"gen-{run_id}-r{rnd}-{time.strftime('%H%M%S')}", systems.get("mutants"))
                record["mutation"] = mut["results"]
                blocking = [x for x in mut["survived"] if x.get("verdict") == "survived"]
                tolerated = [x for x in mut["survived"] if x.get("verdict") != "survived"]
                if len(blocking) <= MUTANT_TOLERANCE:
                    tolerated, blocking = tolerated + blocking, []
                if tolerated:  # test weaknesses, recorded in the VERDICT, not a repair round (MUTANT_TOLERANCE)
                    record["mutants_tolerated"] = [{k: x.get(k) for k in ("fault", "verdict", "wrong_fix", "failed_names", "named_tests")}
                                                   for x in tolerated]
                    log.event("mutants_tolerated", faults=[x["fault"] for x in tolerated],
                              verdicts=[x.get("verdict") for x in tolerated])
                if blocking:
                    mutation_only = True
                    error = ("The tests do not catch these plausible incomplete fixes (each one was run as "
                             "solve.sh and ALL tests passed):\n- "
                             + "\n- ".join(f"fault {x['fault']}: {x['wrong_fix']}"
                                            + (f"\n  Case the tests miss (write a test for it): {x['distinguishing_case']}"
                                               if x.get("distinguishing_case") else "")
                                            for x in blocking)
                             + "\nAdd or strengthen a test for each: it must run that fault's counterexample "
                               "through the program's public behaviour and fail the incomplete fix, and it "
                               "must follow from instruction.md's goal. Keep the correct solution passing.")
        summary["rounds"].append(record)
        log.event("checks", round=rnd, passed=not error,
                  results={c["name"]: c["reward"] if c["name"] != "validator" else c["passed"]
                           for c in record["checks"]},
                  gate=[g[:200] for g in gate], missing=[m[:120] for m in missing])
        if not error:
            summary["task_dir"] = task_dir
            return finish("ok", task_name=f"{TASK_ORG}/{task_name}")
        if rnd == last_round:
            # One bonus round when only the mutation check failed: the task is otherwise correct,
            # and a missing test is a small, targeted repair (the renderer lost a good design here).
            if mutation_only and not bonus_used and BONUS_REPAIR_ROUND:
                last_round, bonus_used = last_round + 1, True
                log.event("bonus_repair_round", round=rnd + 1)
            else:
                break
        try:
            patch, _, _ = chat(systems["repair"], prompts.repair_user(spec, files, error),
                               parse_file_blocks, log.llm, f"repair-r{rnd + 1}")
        except LLMError as e:
            summary["error"] = str(e)
            break
        fixed, dropped = clean_files(patch)
        files.update(fixed)

    # Failed: keep the last attempt in the logs, not in output/, so output/ only holds good tasks.
    if os.path.isdir(task_dir):
        last = os.path.join(log.dir, "last-attempt")
        shutil.rmtree(last, ignore_errors=True)  # a resumed run's newer attempt replaces it
        shutil.move(task_dir, last)
    return finish("failed")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Harbor (Terminal-Bench 2) task from a topic, then check it "
                    "with the validator, oracle and nop.",
        epilog='example: python generate.py "fix a memory bug in a C ring buffer"',
    )
    parser.add_argument("topic", nargs="?", default="fix a broken Python CLI",
                        help="short description of the task to generate (default: %(default)r)")
    parser.add_argument("-o", "--output-dir",
                        help="where to write the task (default: output/<task-name from the spec>)")
    args = parser.parse_args()

    result = generate_task(args.topic, args.output_dir)
    print(json.dumps({k: result.get(k) for k in ("status", "task_dir", "logs_dir", "tokens", "seconds")}, indent=2))
    if result["status"] == "ok":
        print(f"Generated task at: {result['task_dir']}")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
