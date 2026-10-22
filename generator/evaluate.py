"""
Band eval: is a task learnable for the reference agent?

  run_band()  runs EVAL_AGENT + EVAL_MODEL (terminus-2 + glm-5.3-flash, reasoning high)
              N_RUNS times and counts passes:
                  0            -> too_hard
                  1..3         -> learnable      (BAND_LOW..BAND_HIGH)
                  4..5         -> too_easy
              Timeouts and infra errors are "invalid", not failures (a timeout is not
              the model failing). They are replaced by extra runs, up to
              MAX_INVALID_RERUNS; if N valid runs still can't be reached -> inconclusive.

  triage()    asks the authoring model whether each failed run was the model's fault
              or the task's, so every shipped task has a known failure reason.
"""

import glob
import json
import math
import os
import posixpath
import re
import statistics
import time
from dataclasses import asdict, dataclass, field

import prompts
from checks import _pytest_excerpt, _read, _tail, harbor_run, remove_containers
from config import (
    BAND_HIGH,
    BAND_LOW,
    ENV_FILE,
    EVAL_AGENT,
    EVAL_CONCURRENCY,
    EVAL_MODEL,
    EVAL_REASONING_EFFORT,
    JOBS_DIR,
    MAX_INVALID_RERUNS,
    N_RUNS,
)
from difficulty import is_code_or_config, shipped_names
from llm import LLMError, chat, parse_json_object

# Harbor's own per-trial limits: agent 1h, verifier 15 min, build 10 min.
TRIAL_WALL_SEC = 3600 + 900 + 600


@dataclass
class BandResult:
    task_dir: str
    verdict: str = "error"  # too_hard | learnable | too_easy | inconclusive | error
    passes: int = 0
    n_valid: int = 0
    n_invalid: int = 0
    trials: list = field(default_factory=list)
    jobs: list = field(default_factory=list)
    tokens: dict = field(default_factory=lambda: {"input": 0, "output": 0})
    cost_usd: float | None = None
    median_steps: float | None = None
    median_found_step: float | None = None  # first step that mentions a file the fix touches
    early_stop: bool = False  # stopped once BAND_HIGH+1 passes made "too_easy" certain
    seconds: float = 0.0
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def classify_trial(trial: dict) -> tuple[str, str]:
    """Return (outcome, detail): outcome is pass | fail | invalid.

    Any exception makes the run invalid, including an agent timeout that still
    scored 1: the README says timeouts don't count, and an agent that never
    finished didn't cleanly solve the task.
    """
    exc = trial.get("exception_info")
    if exc:
        return "invalid", exc.get("exception_type") or "exception"
    reward = ((trial.get("verifier_result") or {}).get("rewards") or {}).get("reward")
    if reward is None:
        return "invalid", "no reward"
    return ("pass", "") if float(reward) >= 1.0 else ("fail", "")


def verdict_for(passes: int, n_valid: int, n_runs: int = N_RUNS) -> str:
    if n_valid < n_runs:
        return "inconclusive"
    if passes < BAND_LOW:
        return "too_hard"
    if passes > BAND_HIGH:
        return "too_easy"
    return "learnable"


def _failed_tests(trial_dir: str) -> list[str]:
    """Names of the tests a trial failed (from the verifier's CTRF report), kept in band.json
    so the evidence for a verdict survives even if jobs/ is deleted."""
    try:
        tests = json.loads(_read(os.path.join(trial_dir, "verifier", "ctrf.json")) or "{}")["results"]["tests"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return []
    return [t.get("name", "?").rsplit("::", 1)[-1] for t in tests if t.get("status") not in ("passed", "skipped")]


def _collect(job_dir: str) -> list[dict]:
    """Summarise every trial of one harbor job."""
    out = []
    for path in sorted(glob.glob(os.path.join(job_dir, "*", "result.json"))):
        trial = json.loads(_read(path) or "{}")
        outcome, detail = classify_trial(trial)
        agent = trial.get("agent_result") or {}
        out.append({
            "trial_dir": os.path.dirname(path),
            "outcome": outcome,
            "detail": detail,
            "reward": ((trial.get("verifier_result") or {}).get("rewards") or {}).get("reward"),
            "input_tokens": agent.get("n_input_tokens") or 0,
            "output_tokens": agent.get("n_output_tokens") or 0,
            "cost_usd": agent.get("cost_usd"),
            "episodes": (agent.get("metadata") or {}).get("n_episodes"),
            "failed_tests": _failed_tests(os.path.dirname(path)),
        })
    return out


def fault_targets(task_dir: str) -> set[str]:
    """Shipped source/config files that solve.sh mentions (by any path form): the places the
    agent has to find. Data files are left out; they are inputs, not fault locations."""
    solve = _read(os.path.join(task_dir, "solution", "solve.sh"))
    files = {"environment/Dockerfile": _read(os.path.join(task_dir, "environment", "Dockerfile"))}
    for path in glob.glob(os.path.join(task_dir, "environment", "**", "*"), recursive=True):
        if os.path.isfile(path):
            files[os.path.relpath(path, task_dir).replace(os.sep, "/")] = ""
    out = set()
    for name in shipped_names(files):
        if name.startswith("/"):  # explicit COPY destination, e.g. /etc/nginx/sites-available/default
            if name in solve:
                out.add(name)
            continue
        if is_code_or_config(name) and re.search(rf"(?<![\w.-]){re.escape(name)}(?![\w-])", solve):
            out.add(name)
    return out


def _commands(step: dict) -> str:
    """The shell keystrokes an agent step sent (terminus-2 stores them in tool_calls)."""
    return "\n".join(str((c.get("arguments") or {}).get("keystrokes", ""))
                     for c in (step.get("tool_calls") or []) if isinstance(c, dict))


def found_step(trial_dir: str, targets: set[str]) -> int | None:
    """Agent turn (1-based) at which the agent first names a file the fix touches."""
    if not targets:
        return None
    try:
        steps = json.loads(_read(os.path.join(trial_dir, "agent", "trajectory.json")) or "{}").get("steps") or []
    except json.JSONDecodeError:
        return None
    for i, s in enumerate([s for s in steps if s.get("source") == "agent"], start=1):
        msg = s.get("message")
        text = (msg if isinstance(msg, str) else json.dumps(msg)) + "\n" + _commands(s)
        if any(t in text for t in targets):
            return i
    return None


def prior_band_jobs(run_id: str) -> list[str]:
    """Job dirs an earlier (killed) band eval with this run_id left in JOBS_DIR, in order."""
    jobs = glob.glob(os.path.join(JOBS_DIR, f"band-{run_id}-*"))
    return sorted((j for j in jobs if re.fullmatch(r"\d+", j.rsplit("-", 1)[-1])),
                  key=lambda j: int(j.rsplit("-", 1)[-1]))


def run_band(task_dir: str, run_id: str, n_runs: int = N_RUNS, log=None, on_start=None) -> BandResult:
    """Run the reference agent until n_runs valid trials exist (or reruns run out).

    Resumable: trials that finished under the same run_id before a kill are counted and only
    the missing runs are launched; their unfinished trials' containers are removed."""
    started = time.time()
    res = BandResult(task_dir=task_dir)
    to_run, extra_left, k = n_runs, MAX_INVALID_RERUNS, 0
    for job_dir in prior_band_jobs(run_id):
        done = _collect(job_dir)
        res.trials.extend(done)
        res.jobs.append(job_dir)
        k = int(job_dir.rsplit("-", 1)[-1]) + 1
        unfinished = [os.path.basename(os.path.dirname(c)) for c in glob.glob(os.path.join(job_dir, "*", "config.json"))
                      if not os.path.exists(os.path.join(os.path.dirname(c), "result.json"))]
        remove_containers(unfinished)
        if log:
            log("band_resume", job=job_dir, reused=[t["outcome"] for t in done], dropped=len(unfinished))
    if res.trials:
        # Same totals as an uninterrupted eval: at most n_runs + MAX_INVALID_RERUNS finished trials.
        budget = n_runs + MAX_INVALID_RERUNS - len(res.trials)
        valid = [t for t in res.trials if t["outcome"] != "invalid"]
        too_easy = sum(t["outcome"] == "pass" for t in res.trials) > BAND_HIGH
        to_run = 0 if too_easy else max(0, min(n_runs - len(valid), budget))
        extra_left = max(0, budget - to_run)
    while to_run > 0:
        job_name = f"band-{run_id}-{k}"
        conc = max(1, min(EVAL_CONCURRENCY, to_run))
        args = ["-a", EVAL_AGENT, "-m", EVAL_MODEL,
                "--ak", f"reasoning_effort={EVAL_REASONING_EFFORT}",
                "--n-attempts", str(to_run), "--n-concurrent", str(conc),
                "--env-file", ENV_FILE]
        timeout = math.ceil(to_run / conc) * TRIAL_WALL_SEC + 600
        prior_passes = sum(t["outcome"] == "pass" for t in res.trials)

        def too_easy_certain(jd, prior=prior_passes):
            # BAND_HIGH+1 valid passes means too_easy whatever the remaining runs do.
            return prior + sum(t["outcome"] == "pass" for t in _collect(jd)) > BAND_HIGH

        cli_out, job_dir = harbor_run(task_dir, job_name, args, timeout=timeout, stop_when=too_easy_certain,
                                      on_start=on_start)
        trials = _collect(job_dir)
        res.jobs.append(job_dir)
        if log:
            log("band_job", job=job_dir, requested=to_run,
                outcomes=[t["outcome"] + (f"({t['detail']})" if t["detail"] else "") for t in trials])
        if not trials:  # harbor itself failed (bad config, docker down): don't loop
            res.error = "harbor produced no trials:\n" + _tail(cli_out, 3000)
            break
        res.trials.extend(trials)
        if sum(t["outcome"] == "pass" for t in res.trials) > BAND_HIGH:
            res.early_stop = "stopped early" in cli_out
            break
        valid = [t for t in res.trials if t["outcome"] != "invalid"]
        missing = n_runs - len(valid)
        if missing <= 0:
            break
        to_run = min(missing, extra_left)
        extra_left -= to_run
        k += 1

    valid = [t for t in res.trials if t["outcome"] != "invalid"][:n_runs]
    res.n_valid = len(valid)
    res.n_invalid = sum(t["outcome"] == "invalid" for t in res.trials)
    res.passes = sum(t["outcome"] == "pass" for t in valid)
    res.verdict = ("error" if res.error else "too_easy" if res.passes > BAND_HIGH
                   else verdict_for(res.passes, res.n_valid, n_runs))
    res.tokens = {"input": sum(t["input_tokens"] for t in res.trials),
                  "output": sum(t["output_tokens"] for t in res.trials)}
    targets = fault_targets(task_dir)
    for t in res.trials:
        t["found_step"] = found_step(t["trial_dir"], targets)
    steps = [t["episodes"] for t in valid if t["episodes"]]
    found = [t["found_step"] for t in valid if t["found_step"]]
    res.median_steps = statistics.median(steps) if steps else None
    res.median_found_step = statistics.median(found) if found else None
    costs = [t["cost_usd"] for t in res.trials if t["cost_usd"] is not None]
    res.cost_usd = round(sum(costs), 4) if costs else None
    res.seconds = round(time.time() - started, 1)
    return res


def trajectory_tail(trial_dir: str, n_steps: int = 15, max_chars: int = 9000) -> str:
    """The agent's last steps (what it sent, what the terminal showed), compact."""
    path = os.path.join(trial_dir, "agent", "trajectory.json")
    try:
        steps = json.loads(_read(path) or "{}").get("steps") or []
    except json.JSONDecodeError:
        return "(trajectory unreadable)"
    lines = []
    for s in [s for s in steps if s.get("source") == "agent"][-n_steps:]:
        msg = s.get("message")
        msg = msg if isinstance(msg, str) else json.dumps(msg)
        obs = " | ".join(str(r.get("content", ""))
                         for r in ((s.get("observation") or {}).get("results") or []))
        cmds = _commands(s)
        lines.append(f"[step {s.get('step_id')}] AGENT: {msg[:600]}\n  COMMANDS: {cmds[:500]}"
                     f"\n  TERMINAL: {obs[-700:]}")
    return _tail("\n".join(lines), max_chars) if lines else "(no agent steps recorded)"


def _parse_triage(text: str) -> dict:
    obj = parse_json_object(text)
    if obj.get("fault") not in ("model", "task", "unknown"):
        raise ValueError("fault must be 'model', 'task' or 'unknown'")
    as_list = lambda v: [str(x) for x in v] if isinstance(v, list) else ([str(v)] if v else [])
    return {"fault": obj["fault"], "category": str(obj.get("category", "")),
            "reason": str(obj.get("reason", "")), "evidence": as_list(obj.get("evidence")),
            "failed_requirements": as_list(obj.get("failed_requirements"))}


def triage(task_dir: str, failed_trials: list[dict], log=None) -> list[dict]:
    """One authoring-model call per failed run: whose fault was it?"""
    instruction = _read(os.path.join(task_dir, "instruction.md"))
    tests = _read(os.path.join(task_dir, "tests", "test_outputs.py"))
    out = []
    for t in failed_trials:
        test_out = _pytest_excerpt(_read(os.path.join(t["trial_dir"], "verifier", "test-stdout.txt")), 4000)
        user = prompts.triage_user(instruction, tests, test_out, trajectory_tail(t["trial_dir"]))
        try:
            verdict, _, _ = chat(prompts.TRIAGE_SYSTEM, user, _parse_triage, log,
                                 f"triage-{os.path.basename(t['trial_dir'])}")
        except LLMError as e:
            verdict = {"fault": "unknown", "category": "triage-error", "reason": str(e)[:300]}
        out.append({"trial": os.path.basename(t["trial_dir"]), **verdict})
    return out
