"""
Batch pipeline (README Parts 2-4): generate -> band eval -> triage -> keep or reject -> report.

    python pipeline.py --topics ../scripts/topics.txt        # generate + evaluate each topic
    python pipeline.py --topics FILE --batch-id B             # resumes B if it already has state
    python pipeline.py --resume B                             # same, using B's stored topic list
    python pipeline.py --report B                             # rebuild B's report, no model/Docker
    python pipeline.py --eval-only ../output/<task> ...      # evaluate existing tasks
    python pipeline.py --smoke ../output/<task>              # one eval run, config check only
    python pipeline.py --topics FILE --limit 1 --control     # A/B control: no difficulty lever

A task is kept only if it is learnable (BAND_LOW..BAND_HIGH passes of N_RUNS valid runs)
AND triage blames every failed run on the model. Kept tasks stay in output/<task>/ with a
band.json and VERDICT.md; everything else moves to output/_rejected/<task>/.

Robustness (Part 4): every topic's progress lives in the batch ledger (ledger.py), so a killed
batch resumes where it stopped: finished model calls come from the reply cache, finished agent
trials are reused, and only what is missing is paid for. Two copies on the same batch split the
topics through per-topic locks; output dirs, job names and shared files are race-free.
"""

import argparse
import glob
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import tomllib

import prompts
from checks import CHILDREN, kill_tree
from config import (
    BAND_HIGH,
    BAND_LOW,
    CALIBRATION_FILE,
    CALIBRATION_WINDOW,
    CRITIC_FOUND_WITHIN,
    EVAL_MODEL,
    EVAL_PRICE_IN_PER_M,
    EVAL_PRICE_OUT_PER_M,
    EVAL_REASONING_EFFORT,
    GEN_PRICE_IN_PER_M,
    GEN_PRICE_OUT_PER_M,
    LOGS_DIR,
    MAX_FAULTS,
    MAX_LEAKED_LITERALS,
    MIN_ENV_LINES,
    MIN_FAULT_LAYERS,
    MIN_FAULTS,
    MIN_SOLVE_LINES,
    MODEL,
    N_RUNS,
    REJECTED_DIR,
    REPORTS_DIR,
)
from difficulty import env_lines, solve_lines
from evaluate import TRIAL_WALL_SEC, _collect, prior_band_jobs, run_band, triage
from generate import RunLog, generate_task
from ledger import Ledger, file_lock, reserve_dir, write_json_atomic, write_text_atomic

# The knob values a task was generated under, recorded with its verdict: the values in
# difficulty.toml can change between runs.
ORPHAN_POLL_SEC = float(os.environ.get("ORPHAN_POLL_SEC", "15"))  # resume: check an adopted harbor job

KNOBS = {"min_faults": MIN_FAULTS, "max_faults": MAX_FAULTS, "min_fault_layers": MIN_FAULT_LAYERS,
         "min_env_lines": MIN_ENV_LINES, "min_solve_lines": MIN_SOLVE_LINES,
         "max_leaked_literals": MAX_LEAKED_LITERALS, "critic_found_within": CRITIC_FOUND_WITHIN}


def load_history() -> list[dict]:
    try:
        with open(CALIBRATION_FILE, encoding="utf-8") as f:
            rows = [json.loads(l) for l in f if l.strip()]
    except FileNotFoundError:
        return []
    # Only evaluated tasks steer the next design; generation failures are recorded but not fed back.
    return [r for r in rows if r.get("passes") is not None][-CALIBRATION_WINDOW:]


def append_history(entry: dict) -> None:
    """Locked append; an entry whose run_id is already present (a resumed topic) is skipped."""
    os.makedirs(os.path.dirname(CALIBRATION_FILE), exist_ok=True)
    with file_lock(CALIBRATION_FILE + ".lock"):
        if entry.get("run_id") and os.path.exists(CALIBRATION_FILE):
            with open(CALIBRATION_FILE, encoding="utf-8") as f:
                if any(json.loads(l).get("run_id") == entry["run_id"] for l in f if l.strip()):
                    return
        with open(CALIBRATION_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


def _task_meta(task_dir: str) -> dict:
    with open(os.path.join(task_dir, "task.toml"), "rb") as f:
        cfg = tomllib.load(f)
    return {"name": os.path.basename(task_dir),
            "description": (cfg.get("task") or {}).get("description", ""),
            "difficulty": (cfg.get("metadata") or {}).get("difficulty", "")}


def task_features(task_dir: str, spec: dict | None = None) -> dict:
    """What the task actually has (not what the gates asked for), logged with its verdict so
    later analysis can see which features predict difficulty."""
    files = {}
    for path in glob.glob(os.path.join(task_dir, "environment", "**", "*"), recursive=True):
        if os.path.isfile(path):
            with open(path, encoding="utf-8", errors="replace") as f:
                files[os.path.relpath(path, task_dir).replace(os.sep, "/")] = f.read()
    try:
        with open(os.path.join(task_dir, "solution", "solve.sh"), encoding="utf-8") as f:
            solve = f.read()
    except FileNotFoundError:
        solve = ""
    faults = (spec or {}).get("faults") or []
    return {"env_lines": env_lines(files), "solve_lines": solve_lines(solve),
            "faults": len(faults) if spec else None,
            "fault_layers": len({str(f.get("layer")) for f in faults if isinstance(f, dict)}) if spec else None}


def evaluate_task(task_dir: str, log: RunLog, arm: str = "treatment", spec: dict | None = None,
                  run_id: str | None = None, on_start=None) -> dict:
    """Band-eval one task, triage it if learnable, then keep or reject it.
    Control-arm results are recorded but kept out of the calibration history.
    With the run_id of a killed eval, its finished trials are reused (evaluate.run_band)."""
    task_dir = os.path.abspath(task_dir)
    meta = _task_meta(task_dir)
    features = task_features(task_dir, spec)
    run_id = run_id or f"{meta['name']}-{time.strftime('%Y%m%d-%H%M%S')}-{os.urandom(2).hex()}"
    log.event("band_start", task=meta["name"], run_id=run_id)
    band = run_band(task_dir, run_id, log=log.event, on_start=on_start)

    valid = [t for t in band.trials if t["outcome"] != "invalid"][:N_RUNS]
    failures = []
    if band.verdict == "learnable":
        failures = triage(task_dir, [t for t in valid if t["outcome"] == "fail"], log.llm)
    task_faults = [f for f in failures if f["fault"] == "task"]
    unknown = [f for f in failures if f["fault"] not in ("model", "task")]

    if band.verdict != "learnable":
        decision, why = "rejected", band.verdict + (
            f" (stopped early after {band.passes} passes)" if band.early_stop else "")
    elif task_faults:
        decision, why = "rejected", "unfair: " + "; ".join(f["reason"] for f in task_faults)[:300]
    elif unknown:  # README: know why every shipped task fails; an unexplained failure isn't shipped
        decision, why = "review", "triage could not explain: " + "; ".join(
            f"{f['trial']}: {f['reason']}" for f in unknown)[:400]
    else:
        decision, why = "kept", "learnable; failures: " + "; ".join(dict.fromkeys(
            f"{f['category']}: {f['reason']}" for f in failures))[:500]

    record = {**meta, "arm": arm, "run_id": run_id, "features": features, "verdict": band.verdict,
              "passes": band.passes, "n_valid": band.n_valid, "n_invalid": band.n_invalid,
              "decision": decision, "why": why, "triage": failures, "band": band.to_dict(),
              "eval_model": EVAL_MODEL, "reasoning_effort": EVAL_REASONING_EFFORT}
    with open(os.path.join(task_dir, "band.json"), "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    if decision == "rejected":
        dest = reserve_dir(os.path.join(REJECTED_DIR, meta["name"]))
        os.rmdir(dest)  # reserved the name; move the task into it
        shutil.move(task_dir, dest)
        record["task_dir"] = dest
    else:
        record["task_dir"] = task_dir

    if band.verdict != "error" and arm != "control":
        note = ("UNFAIR, rejected: " + task_faults[0]["category"]) if task_faults else (
            failures[0]["category"] if failures else "")
        if band.median_steps:  # concrete evidence for the next design, not just "5/5"
            note = (note + "; " if note else "") + f"agent median {band.median_steps:g} steps"
            if band.median_found_step:
                note += f", reached the faulty files on turn {band.median_found_step:g}"
        append_history({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "run_id": run_id, "knobs": KNOBS,
                        "name": meta["name"], "description": meta["description"],
                        "difficulty": meta["difficulty"], "passes": band.passes, "n": N_RUNS,
                        "challenge_kind": (spec or {}).get("challenge_kind"),
                        "verdict": band.verdict, "note": note, "features": features,
                        "median_steps": band.median_steps, "median_found_step": band.median_found_step,
                        "cost_usd": band.cost_usd})
    log.event("band_done", task=meta["name"], verdict=band.verdict, passes=band.passes,
              decision=decision)
    return record


# --- cost and time (Part 3) ---------------------------------------------------------------

def _events(logs_dir: str | None) -> list[dict]:
    try:
        with open(os.path.join(logs_dir or "", "events.jsonl"), encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def llm_spend(logs_dir: str | None, labels=None) -> dict:
    """Every glm call logged in a logs dir, including failed attempts and calls from a killed
    run: what was actually paid. Gateway-reported cost wins; otherwise tokens x list price."""
    tin = tout = 0
    reported = 0.0
    for e in _events(logs_dir):
        if e.get("event") != "llm_call" or (labels and not str(e.get("label", "")).startswith(labels)):
            continue
        u = e.get("usage") or {}
        tin += u.get("prompt_tokens") or 0
        tout += u.get("completion_tokens") or 0
        reported += u.get("cost_usd") or 0.0
    priced = (tin * GEN_PRICE_IN_PER_M + tout * GEN_PRICE_OUT_PER_M) / 1e6
    return {"input": tin, "output": tout, "cost_usd": round(reported or priced, 4),
            "cost_source": "gateway" if reported else "list price"}


def eval_cost(band: dict) -> float:
    if band.get("cost_usd") is not None:
        return band["cost_usd"]
    tok = band.get("tokens") or {}
    return round(((tok.get("input") or 0) * EVAL_PRICE_IN_PER_M + (tok.get("output") or 0) * EVAL_PRICE_OUT_PER_M) / 1e6, 4)


def _span_seconds(events: list[dict]) -> float:
    times = [time.mktime(time.strptime(e["time"], "%Y-%m-%dT%H:%M:%S")) for e in events if e.get("time")]
    return round(max(times) - min(times), 1) if times else 0.0


# --- the audit record a reader can check without reading code (Part 4) -------------------

def funnel_flags(state: dict) -> dict:
    """Which stages a topic reached, from its gen summary and record."""
    gen = state.get("gen") or {}
    rec = state.get("record") or {}
    rounds = gen.get("rounds") or []
    checks = [c for r in rounds for c in r.get("checks") or []]
    logs = gen.get("logs_dir") or state.get("logs_dir")
    return {
        "spec_ok": bool(logs and os.path.exists(os.path.join(logs, "spec.json"))),
        "files_written": bool(rounds),
        "structural": any(c.get("name") == "validator" and c.get("passed") for c in checks),
        "correct": gen.get("status") == "ok",
        "evaluated": rec.get("verdict") in ("too_hard", "learnable", "too_easy"),
        "learnable": rec.get("verdict") == "learnable",
        "kept": rec.get("decision") == "kept",
        "review": rec.get("decision") == "review",
    }


def verdict_md(state: dict) -> str:
    gen = state.get("gen") or {}
    rec = state.get("record") or {}
    logs = gen.get("logs_dir") or state.get("logs_dir") or ""
    lines = [f"# Verdict: {rec.get('decision', state.get('stage'))}", "",
             f"- Topic: {state['topic']}", f"- Task: {rec.get('name') or '-'}",
             f"- Why: {rec.get('why') or gen.get('error') or '-'}",
             f"- Generator: `{MODEL}`; eval: `{EVAL_MODEL}`, reasoning_effort={EVAL_REASONING_EFFORT}, "
             f"{N_RUNS} runs, learnable = {BAND_LOW}-{BAND_HIGH} passes", "", "## Generation", ""]
    for e in _events(logs):
        if e.get("event") == "spec_gate":
            lines.append(f"- spec gate (attempt {e.get('attempt')}): "
                         + ("pass" if not e.get("problems") else "; ".join(e["problems"])[:400]))
        elif e.get("event") in ("critic", "discovery_eval", "instruction_review"):
            lines.append(f"- {e['event']}: {json.dumps({k: e[k] for k in e if k not in ('time', 'event')})[:400]}")
    for r in gen.get("rounds") or []:
        checks = ", ".join(f"{c['name']}={'pass' if c.get('passed') else 'FAIL'}"
                           + (f" (reward {c['reward']})" if c.get("reward") is not None else "")
                           for c in r.get("checks") or []) or "not run"
        gate = "; ".join(r.get("difficulty_gate") or []) or "pass"
        lines.append(f"- round {r['round']}: difficulty gate: {gate[:300]} | checks: {checks}")
    lines.append(f"- result: {gen.get('status', '-')}")
    band = rec.get("band") or {}
    if band.get("trials"):
        triage_by = {t.get("trial"): t for t in rec.get("triage") or []}
        lines += ["", f"## Band eval: {rec.get('passes')}/{rec.get('n_valid')} passed "
                      f"({rec.get('n_invalid')} invalid re-run) -> {rec.get('verdict')}", "",
                  "| trial | outcome | steps | cost | failed tests | triage |", "|---|---|---|---|---|---|"]
        for t in band["trials"]:
            name = os.path.basename(t["trial_dir"])
            tri = triage_by.get(name)
            lines.append(f"| {name} | {t['outcome']}{' (' + t['detail'] + ')' if t.get('detail') else ''} | "
                         f"{t.get('episodes') or '-'} | {t.get('cost_usd') or '-'} | "
                         f"{', '.join(t.get('failed_tests') or []) or '-'} | "
                         f"{(tri['fault'] + ': ' + tri['reason']).replace('|', '/')[:200] if tri else '-'} |")
    lines += ["", "## Evidence", "", f"- generation log: `{logs}` (events.jsonl, raw model replies, spec.json)"]
    for j in band.get("jobs") or []:
        lines.append(f"- harbor job: `{j}`")
    return "\n".join(lines) + "\n"


# --- one topic, resumable -------------------------------------------------------------------

def _adopt_orphan_harbor(pid: int | None, run_id: str, ledger: Ledger, topic: str) -> None:
    """A `kill -9` of the pipeline kills only Python: its harbor child keeps running the agent
    trials (their conversations live in harbor's memory). Instead of killing that job and
    re-paying for its trials, wait for it to finish; run_band then collects its results as
    finished trials. Early stop still applies while waiting. Checked by command line, so a
    reused pid is never mistaken for our job."""
    if not pid:
        return
    def ours() -> bool:
        cmd = subprocess.run(["ps", "-ww", "-o", "command=", "-p", str(pid)], capture_output=True, text=True).stdout
        return "harbor" in cmd and f"band-{run_id}-" in cmd
    if not ours():
        return
    ledger.audit("adopt_orphan_harbor", topic=topic, harbor_pid=pid, run_id=run_id)
    deadline = time.time() + TRIAL_WALL_SEC + 600
    while ours():
        passes = sum(t["outcome"] == "pass" for j in prior_band_jobs(run_id) for t in _collect(j))
        if passes > BAND_HIGH or time.time() > deadline:  # verdict certain, or the job hung
            kill_tree(pid)
            break
        time.sleep(ORPHAN_POLL_SEC)
    ledger.audit("orphan_harbor_done", topic=topic, harbor_pid=pid)


def _recover_moved_record(state: dict) -> dict | None:
    """Killed after the task was moved to _rejected/ but before the ledger said so."""
    for path in glob.glob(os.path.join(REJECTED_DIR, "*", "band.json")):
        with open(path, encoding="utf-8") as f:
            rec = json.load(f)
        if rec.get("run_id") == state.get("run_id"):
            return {**rec, "task_dir": os.path.dirname(path)}
    return None


def process_topic(topic: str, ledger: Ledger, log: RunLog, control: bool) -> dict:
    arm = "control" if control else "treatment"
    st = ledger.get(topic)
    if st["stage"] in ("done", "gen_failed"):
        return st["record"]

    if st["stage"] in ("pending", "generating"):
        if "calibration" not in st:  # fixed at first start, so a resumed spec prompt is identical
            calibration = "" if control else prompts.calibration_block(load_history())
            st = ledger.set(topic, "generating", calibration=calibration, arm=arm)
        else:
            ledger.audit("resume", topic=topic, key=st["key"], stage=st["stage"], logs_dir=st.get("logs_dir"))
        gen = generate_task(topic, calibration=st["calibration"], control=control,
                            resume_dir=st.get("logs_dir"), on_start=lambda d: ledger.update(topic, logs_dir=d))
        gen = {k: gen.get(k) for k in ("status", "task_dir", "logs_dir", "run_id", "rounds", "error",
                                       "tokens", "seconds", "task_name")}
        if gen["status"] != "ok":
            record = {"topic": topic, "arm": arm, "stage": "generate", "verdict": "gen_failed",
                      "decision": "rejected", "why": "failed generation: " + str(gen.get("error") or "Part 1 checks")[:200],
                      "logs_dir": gen["logs_dir"]}
            if not control:  # a design glm-5.1 can't build is recorded too
                append_history({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "run_id": gen["run_id"],
                                "knobs": KNOBS, "name": topic[:60], "verdict": "gen_failed", "passes": None})
            st = ledger.set(topic, "gen_failed", why=record["why"][:120], gen=gen, record=record)
            write_text_atomic(os.path.join(gen["logs_dir"], "VERDICT.md"), verdict_md(st))
            return record
        st = ledger.set(topic, "generated", why=gen["task_dir"], gen=gen)

    gen = st["gen"]
    if st["stage"] == "generated":
        run_id = f"{os.path.basename(gen['task_dir'])}-{time.strftime('%Y%m%d-%H%M%S')}-{os.urandom(2).hex()}"
        st = ledger.set(topic, "evaluating", why=run_id, run_id=run_id)
    else:  # evaluating: resume the same run_id, first letting a killed run's harbor job finish
        _adopt_orphan_harbor(st.get("harbor_pid"), st["run_id"], ledger, topic)
        ledger.audit("resume", topic=topic, key=st["key"], stage="evaluating", run_id=st["run_id"])
        if not os.path.isdir(gen["task_dir"]):
            rec = _recover_moved_record(st)
            if rec:
                record = {**rec, "topic": topic, "stage": "eval", "gen_logs_dir": gen["logs_dir"]}
                st = ledger.set(topic, "done", why=record["decision"], record=record)
                write_text_atomic(os.path.join(record["task_dir"], "VERDICT.md"), verdict_md(st))
                return record
    spec = None
    try:
        with open(os.path.join(gen["logs_dir"], "spec.json"), encoding="utf-8") as f:
            spec = json.load(f)
    except FileNotFoundError:
        pass
    rec = evaluate_task(gen["task_dir"], log, arm, spec, run_id=st["run_id"],
                        on_start=lambda pid: ledger.update(topic, harbor_pid=pid))
    record = {**rec, "topic": topic, "stage": "eval", "gen_logs_dir": gen["logs_dir"]}
    st = ledger.set(topic, "done", why=record["decision"], record=record, harbor_pid=None)
    write_text_atomic(os.path.join(record["task_dir"], "VERDICT.md"), verdict_md(st))
    return record


# --- report (Part 3) ------------------------------------------------------------------------

def write_report(batch_id: str, ledger: Ledger | None = None, records: list[dict] | None = None) -> str:
    """Batch report from the ledger (all topics, whichever copy processed them), or from plain
    records for --eval-only runs."""
    states = ledger.all_states() if ledger else [{"topic": r.get("name"), "stage": "done", "record": r}
                                                 for r in records or []]
    if ledger:  # keep the topic-file order
        order = {t: i for i, t in enumerate(ledger.stored_topics())}
        states.sort(key=lambda s: order.get(s["topic"], 1e9))
    rows = []
    for s in states:
        rec, gen = s.get("record") or {}, s.get("gen") or {}
        gcost = llm_spend(gen.get("logs_dir") or s.get("logs_dir"))
        band = rec.get("band") or {}
        rows.append({"state": s, "rec": rec, "flags": funnel_flags(s), "gen_cost": gcost,
                     "eval_cost": eval_cost(band) if band else 0.0,
                     "gen_sec": _span_seconds(_events(gen.get("logs_dir") or s.get("logs_dir"))),
                     "eval_sec": band.get("seconds") or 0.0})
    triage_cost = llm_spend(os.path.join(os.path.abspath(LOGS_DIR), batch_id), "triage")["cost_usd"]
    n = len(rows)
    count = lambda k: sum(r["flags"][k] for r in rows)
    pct = lambda a, b: f"{100 * a / b:.0f}%" if b else "-"
    total_gen = sum(r["gen_cost"]["cost_usd"] for r in rows)
    total_eval = sum(r["eval_cost"] for r in rows)
    total = total_gen + total_eval + triage_cost
    kept = count("kept")
    audit = os.path.join(ledger.dir, "audit.jsonl") if ledger else ""
    wall = _span_seconds([json.loads(l) for l in open(audit, encoding="utf-8")]) if audit and os.path.exists(audit) else 0
    done = sum(r["state"].get("stage") in ("done", "gen_failed") for r in rows)

    evaluated = [r["rec"] for r in rows if r["flags"]["evaluated"]]
    hist = {k: sum(1 for r in evaluated if r.get("passes") == k) for k in range(N_RUNS + 1)}
    lines = [f"# Batch {batch_id}", "",
             f"Generator `{MODEL}`. Eval `{EVAL_MODEL}`, reasoning_effort={EVAL_REASONING_EFFORT}, "
             f"{N_RUNS} runs per task; learnable = {BAND_LOW}-{BAND_HIGH} passes.",
             f"Topics finished: {done} / {n}" + ("" if done == n else " (batch still running or was killed; "
                                                    "`--resume` continues it)"), "",
             "## Funnel", "", "| stage | tasks | of topics |", "|---|---|---|"]
    for label, key in (("spec passed the difficulty gate", "spec_ok"), ("files written", "files_written"),
                       ("structural validation passed", "structural"),
                       ("functionally correct (oracle 1, nop 0)", "correct"),
                       ("band-evaluated", "evaluated"), (f"learnable ({BAND_LOW}-{BAND_HIGH}/{N_RUNS})", "learnable"),
                       ("kept (learnable, every failure the model's fault)", "kept"),
                       ("needs review (triage could not explain a failure)", "review")):
        lines.append(f"| {label} | {count(key)} | {pct(count(key), n)} |")
    lines += ["", f"**Yield: {kept} / {n} topics kept ({pct(kept, n)}); "
                  f"{count('learnable')} / {count('correct')} correct tasks learnable "
                  f"({pct(count('learnable'), count('correct'))}).**", "",
              "## Pass distribution (evaluated tasks)", "",
              "| passes | " + " | ".join(f"{k}/{N_RUNS}" for k in hist) + " |",
              "|---|" + "---|" * len(hist), "| tasks | " + " | ".join(str(v) for v in hist.values()) + " |",
              "(A too-easy eval stops early once 4 passes make the verdict certain; it counts at the passes reached.)", "",
              "## Cost and time", "",
              f"- Generation ({MODEL}): ${total_gen:.2f}",
              f"- Band eval ({EVAL_MODEL}): ${total_eval:.2f}",
              f"- Triage ({MODEL}): ${triage_cost:.2f}",
              f"- **Total: ${total:.2f}**; per topic ${total / n:.2f}" if n else "- Total: $0",
              f"- Per kept task: ${total / kept:.2f}" if kept else "- Per kept task: - (none kept)",
              f"- Wall clock: {wall / 3600:.1f} h (first to last audit line); summed stage time "
              f"{sum(r['gen_sec'] + r['eval_sec'] for r in rows) / 3600:.1f} h",
              f"- Prices: gateway-reported cost when present, else list prices per 1M tokens: "
              f"{MODEL} ${GEN_PRICE_IN_PER_M} in / ${GEN_PRICE_OUT_PER_M} out, "
              f"{EVAL_MODEL} ${EVAL_PRICE_IN_PER_M} / ${EVAL_PRICE_OUT_PER_M} (eval uses Harbor's reported cost when present).",
              "", "## Tasks", "",
              "| topic | task | stage | verdict | passes | decision | gen $ / min | eval $ / min | why | verdict file |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        s, rec = r["state"], r["rec"]
        vfile = os.path.join(rec["task_dir"], "VERDICT.md") if rec.get("task_dir") else (
            os.path.join(rec["logs_dir"], "VERDICT.md") if rec.get("logs_dir") else "")
        lines.append(f"| {s['topic'][:60]} | {rec.get('name') or '-'} | {s.get('stage')} | {rec.get('verdict', '-')} | "
                     f"{rec.get('passes', '-')}/{rec.get('n_valid', '-')} | {rec.get('decision', '-')} | "
                     f"${r['gen_cost']['cost_usd']:.2f} / {r['gen_sec'] / 60:.0f} | ${r['eval_cost']:.2f} / {r['eval_sec'] / 60:.0f} | "
                     f"{str(rec.get('why', '')).replace('|', '/')[:160]} | {vfile or '-'} |")
    os.makedirs(REPORTS_DIR, exist_ok=True)
    base = os.path.join(REPORTS_DIR, batch_id)
    with file_lock(base + ".lock"):  # two copies may finish at the same time
        write_json_atomic(base + ".json", [{"topic": r["state"]["topic"], "stage": r["state"].get("stage"),
                                            **r["flags"], "gen_cost": r["gen_cost"], "eval_cost_usd": r["eval_cost"],
                                            "gen_seconds": r["gen_sec"], "eval_seconds": r["eval_sec"],
                                            "record": r["rec"]} for r in rows])
        write_text_atomic(base + ".md", "\n".join(lines) + "\n")
    return base + ".md"


def _install_signal_handlers(ledger: Ledger | None) -> None:
    """SIGTERM/SIGINT: stop harbor children (and their containers' runs) before exiting, so
    nothing keeps running unrecorded. Per-topic flocks are released by the OS on exit."""
    def handler(signum, _frame):
        if ledger:
            ledger.audit("killed", signal=signal.Signals(signum).name, children=sorted(CHILDREN))
        for pid in list(CHILDREN):
            kill_tree(pid, grace=5.0)
        sys.exit(128 + signum)
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate tasks and keep only learnable, fair ones.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--topics", help="file with one topic per line (# comments allowed)")
    src.add_argument("--resume", metavar="BATCH_ID", help="continue a batch with its stored topic list")
    src.add_argument("--report", metavar="BATCH_ID", help="rebuild a batch's report from its ledger only")
    src.add_argument("--eval-only", nargs="+", metavar="TASK_DIR", help="evaluate existing task dirs")
    src.add_argument("--smoke", metavar="TASK_DIR",
                     help="run the eval agent once to check the eval config; no verdict, nothing moved")
    parser.add_argument("--limit", type=int, help="only the first N topics")
    parser.add_argument("--batch-id", help="name for this batch (default: batch-<time>); an existing "
                                           "batch id resumes that batch")
    parser.add_argument("--control", action="store_true",
                        help="A/B control arm: no difficulty rule, no calibration, and results "
                             "are kept out of the calibration history")
    args = parser.parse_args()

    if args.report:
        print(f"Report: {write_report(args.report, Ledger(args.report))}")
        return 0

    batch_id = args.resume or args.batch_id or "batch-" + time.strftime("%Y%m%d-%H%M%S")
    log = RunLog(os.path.join(os.path.abspath(LOGS_DIR), batch_id))

    if args.smoke:
        band = run_band(os.path.abspath(args.smoke), f"smoke-{time.strftime('%H%M%S')}-{os.urandom(2).hex()}",
                        n_runs=1, log=log.event)
        log.write_json("smoke.json", band.to_dict())
        print(json.dumps({k: band.to_dict()[k] for k in ("trials", "tokens", "cost_usd", "seconds", "error")},
                         indent=2))
        return 0 if band.trials else 1

    if args.eval_only:
        _install_signal_handlers(None)
        records = [evaluate_task(task_dir, log) for task_dir in args.eval_only]
        log.write_json("records.json", records)
        print(f"Report: {write_report(batch_id, records=records)}")
        return 0

    ledger = Ledger(batch_id)
    _install_signal_handlers(ledger)
    if args.topics:
        with open(args.topics, encoding="utf-8") as f:
            topics = [l.strip() for l in f if l.strip() and not l.lstrip().startswith("#")]
        ledger.save_topics(topics[: args.limit])
    topics = ledger.stored_topics()[: args.limit]
    ledger.audit("batch_start", batch=batch_id, topics=len(topics), control=args.control)
    skipped = []
    for topic in topics:
        if not ledger.try_lock(topic):  # another copy is working on it
            ledger.audit("skipped_locked", topic=topic)
            skipped.append(topic)
            continue
        try:
            process_topic(topic, ledger, log, args.control)
        finally:
            ledger.unlock(topic)
        write_report(batch_id, ledger)  # refreshed after every topic, so a kill loses nothing
    ledger.audit("batch_end", batch=batch_id, skipped_locked=len(skipped))
    report = write_report(batch_id, ledger)
    print(f"Report: {report}" + (f" ({len(skipped)} topics were being processed by another copy)" if skipped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
