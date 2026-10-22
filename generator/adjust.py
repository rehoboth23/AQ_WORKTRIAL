"""
Difficulty adjustment (stretch goal A): move ONE evaluated task into the 1-3/5 band with small,
fair edits, never by making it unfair.

  mode = adjust_mode(verdict, triage)        harden | ease | fairness | None
  evidence = band_evidence(...)              per-test table, same-failure flag, triage, trajectories
  -> glm-5.1 proposes at most two edits (prompts.ADJUST_SYSTEM)
  -> snapshot, apply, re-check (validator, oracle, nop, mutants); restore the snapshot on failure
  -> re-evaluate (a new band eval); repeat up to config.ADJUST_ROUNDS times

Each round is recorded (mode, edits, removed instruction sentences, checks, pass counts before and
after) so the verdict and the report can show before/after.
"""

import json
import os
import re
import shutil

import prompts
from checks import run_all
from config import ADJUST_MODES, ADJUST_ROUNDS, MUTATION_CHECK
from evaluate import common_failure, review_band, run_band, test_table, trajectory_tail
from generate import CANARY_COMMENT, Spec, chat, mutation_check, write_task
from llm import LLMError, parse_file_blocks

TASK_FILES = ("instruction.md", "environment/", "solution/", "tests/")


def adjust_mode(verdict: str, triage: list[dict]) -> str | None:
    task_faults = [f for f in triage if f.get("fault") == "task"]
    unknown = [f for f in triage if f.get("fault") not in ("model", "task")]
    if verdict in ("learnable", "too_hard") and task_faults:
        mode = "fairness"
    elif verdict == "too_easy":
        mode = "harden"
    elif verdict == "too_hard" and not unknown:
        mode = "ease"
    else:
        return None  # learnable and fair (done), or unexplained failures (needs a human)
    return mode if mode in ADJUST_MODES else None


def load_task_files(task_dir: str) -> dict[str, str]:
    """The model-written files of a task (the inverse of generate.write_task): canary lines
    stripped, task.toml and tests/test.sh left out (Python writes them)."""
    out = {}
    for root, _, names in os.walk(task_dir):
        for n in names:
            path = os.path.join(root, n)
            rel = os.path.relpath(path, task_dir)
            if rel in ("task.toml", "tests/test.sh", "VERDICT.md", "band.json") or not rel.startswith(TASK_FILES):
                continue
            try:
                body = open(path, encoding="utf-8").read()
            except UnicodeDecodeError:
                continue  # binary data files stay on disk untouched
            out[rel] = "".join(l for l in body.splitlines(keepends=True) if l.rstrip("\n") != CANARY_COMMENT)
    return out


def removed_sentences(old: str, new: str) -> list[str]:
    split = lambda t: {s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", t) if len(s.strip()) > 20}
    return sorted(split(old) - split(new))


def band_evidence(band, triage: list[dict]) -> dict:
    trials = [t for t in band.trials if t.get("outcome") in ("pass", "fail")]
    passing = [t for t in trials if t["outcome"] == "pass"][:2]
    failing = [t for t in trials if t["outcome"] == "fail"][:3]
    return {"passes": band.passes, "valid_runs": band.n_valid, "verdict": band.verdict,
            "per_test": test_table(band.trials), "every_failing_run_failed": common_failure(band.trials),
            "triage": [{k: f.get(k) for k in ("trial", "fault", "category", "reason", "requirement_quote")} for f in triage],
            "passing_runs_last_steps": [trajectory_tail(t["trial_dir"], n_steps=25)[-6000:] for t in passing],
            "failing_runs_last_steps": [trajectory_tail(t["trial_dir"])[-4000:] for t in failing]}


def _rewrite(task_dir: str, spec: dict, name: str, files: dict[str, str]) -> None:
    """write_task with the task's own task.toml and tests/test.sh kept byte for byte: an
    adjustment changes the task's content, never its metadata or test runner."""
    keep = {}
    for rel in ("task.toml", "tests/test.sh"):
        path = os.path.join(task_dir, rel)
        if os.path.exists(path):
            keep[rel] = open(path, encoding="utf-8").read()
    defaults = Spec(name=name, description="-").model_dump()  # task.toml fields; the real one is restored below
    write_task(task_dir, {**defaults, **{k: v for k, v in spec.items() if v is not None}}, name, files)
    for rel, body in keep.items():
        with open(os.path.join(task_dir, rel), "w", encoding="utf-8") as f:
            f.write(body)


def adjust_task(task_dir: str, spec: dict, band, review: dict, run_id: str, log, on_start=None,
                rounds: int | None = None) -> tuple:
    """Up to `rounds` adjustment rounds. Returns (band, review, spec, history): the last measured
    version's band result and review, and one record per round."""
    rounds = ADJUST_ROUNDS if rounds is None else rounds
    history, name = [], os.path.basename(task_dir)
    for k in range(1, rounds + 1):
        triage = review["triage"] if band.verdict in ("learnable", "too_hard") else []
        mode = adjust_mode(band.verdict, triage)
        if not mode:
            break
        rec = {"round": k, "mode": mode, "passes_before": band.passes, "verdict_before": band.verdict}
        files = load_task_files(task_dir)
        try:
            raw, _, _ = chat(prompts.ADJUST_SYSTEM, prompts.adjust_user(mode, spec, files, band_evidence(band, triage)),
                             parse_file_blocks, log.llm, f"adjust-r{k}")
            plan = json.loads(raw.pop("adjust.json"))
        except (LLMError, KeyError, ValueError) as e:
            history.append({**rec, "result": "proposal_error", "error": str(e)[:300]}); break
        rec.update(diagnosis=plan.get("diagnosis"), edits=plan.get("edits"))
        if plan.get("give_up"):
            history.append({**rec, "result": "gave_up", "reason": plan["give_up"]}); break
        changed = {p: b for p, b in raw.items() if p.startswith(TASK_FILES) and not p.endswith(("task.toml", "test.sh"))}
        # Only test CODE may change under tests/: expected outputs and fixtures must come from code the
        # tests run, never from the model (it misremembered mawk's integer printing on the first real run).
        rejected = sorted(p for p in changed if p.startswith("tests/") and not p.endswith(".py"))
        changed = {p: b for p, b in changed.items() if p not in rejected}
        if rejected:
            rec["rejected_data_edits"] = rejected
        if not changed:
            history.append({**rec, "result": "no_allowed_edits"}); break
        snap = os.path.join(log.dir, "adjust", f"v{k - 1}")
        if not os.path.isdir(snap):
            shutil.copytree(task_dir, snap)
        new_files = {**files, **changed}
        new_spec = {**spec, **{k2: v for k2, v in (plan.get("spec_patch") or {}).items() if k2 in ("checks", "knobs")}}
        rec["removed_sentences"] = removed_sentences(files.get("instruction.md", ""), new_files.get("instruction.md", ""))
        _rewrite(task_dir, new_spec, name, new_files)
        results = run_all(task_dir, f"adj-{run_id}-r{k}")
        rec["checks"] = {r.name: r.passed for r in results}
        ok = all(r.passed for r in results)
        if ok and MUTATION_CHECK:
            mut = mutation_check(task_dir, new_spec, new_files, log, f"adj-{run_id}-r{k}", prompts.MUTANT_SYSTEM)
            rec["mutants_survived"] = len(mut["survived"])
            ok = not mut["survived"]
        if not ok:  # never keep an edit that broke correctness or left a check untested
            shutil.rmtree(task_dir); shutil.copytree(snap, task_dir)
            history.append({**rec, "result": "checks_failed"}); break
        band = run_band(task_dir, f"{run_id}-adj{k}", log=log.event, on_start=on_start)
        valid = [t for t in band.trials if t["outcome"] != "invalid"]
        review = review_band(task_dir, valid, new_spec, [], log.llm)
        spec = new_spec
        history.append({**rec, "result": "evaluated", "passes_after": band.passes, "verdict_after": band.verdict,
                        "cost_usd": band.cost_usd})
        log.event("adjust_round", **{x: y for x, y in history[-1].items() if x not in ("edits",)})
    return band, review, spec, history
