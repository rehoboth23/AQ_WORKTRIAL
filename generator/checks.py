"""
Correctness checks for a generated task, in order:

  1. structural validator (validator/validate.py)        -> must exit 0
  2. `harbor run -a oracle` (runs solution/solve.sh)    -> reward must be 1
  3. `harbor run -a nop`    (untouched container)       -> reward must be 0

Each check returns a CheckResult; on failure `error` holds the text we send
back to the authoring model for a repair.
"""

import glob
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field

from config import JOBS_DIR, ROOT_DIR

HARBOR = os.path.join(ROOT_DIR, ".venv", "bin", "harbor")
VALIDATOR = os.path.join(ROOT_DIR, "validator", "validate.py")

# The oracle should finish in minutes; cap it at 1/4 of the 1h agent timeout
# so a hanging solve.sh doesn't stall the pipeline.
ORACLE_TIMEOUT_MULTIPLIER = "0.25"
HARBOR_RUN_TIMEOUT_SEC = 3600


@dataclass
class CheckResult:
    name: str
    passed: bool
    reward: float | None = None
    error: str = ""
    job_dir: str | None = None
    seconds: float = 0.0
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _tail(text: str, n: int = 4000) -> str:
    return text if len(text) <= n else "...[truncated]...\n" + text[-n:]


def _pytest_excerpt(text: str, n: int = 5000) -> str:
    """Verifier output from pytest's header onwards, skipping the apt/uv install noise
    test.sh prints first. Falls back to the plain tail if pytest never started."""
    start = text.find("test session starts")
    if start != -1:
        text = text[text.rfind("\n", 0, start) + 1:]
    return _tail(text, n)


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def run_validator(task_dir: str) -> CheckResult:
    started = time.time()
    proc = subprocess.run(
        [sys.executable, VALIDATOR, task_dir],
        cwd=os.path.dirname(VALIDATOR), capture_output=True, text=True,
    )
    out = (proc.stdout + proc.stderr).strip()
    return CheckResult(
        name="validator", passed=proc.returncode == 0,
        error="" if proc.returncode == 0 else "Structural validator failed:\n" + _tail(out),
        seconds=round(time.time() - started, 1), details={"output": _tail(out, 2000)},
    )


def _docker_env() -> dict:
    env = dict(os.environ)
    env["PATH"] = os.path.expanduser("~/.docker/bin") + os.pathsep + env.get("PATH", "")
    return env


def kill_tree(pid: int, grace: float = 10.0) -> None:
    """SIGTERM a process and all its descendants, then SIGKILL whatever is left."""
    import signal
    ps = subprocess.run(["ps", "-eo", "pid=,ppid="], capture_output=True, text=True).stdout
    children: dict[int, list[int]] = {}
    for line in ps.splitlines():
        p, pp = (int(x) for x in line.split())
        children.setdefault(pp, []).append(p)
    tree, stack = [], [pid]
    while stack:
        p = stack.pop()
        tree.append(p)
        stack.extend(children.get(p, []))
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for p in reversed(tree):
            try:
                os.kill(p, sig)
            except ProcessLookupError:
                pass
        if sig == signal.SIGTERM:
            time.sleep(grace)


def remove_containers(prefixes: list[str]) -> list[str]:
    """Force-remove Docker containers whose names start with any prefix (lower-cased, as
    Harbor/compose names them). Used after stopping a run early."""
    prefixes = [p.lower() for p in prefixes if p]
    out = subprocess.run(["docker", "ps", "-a", "--format", "{{.Names}}"], capture_output=True,
                         text=True, env=_docker_env()).stdout
    names = [n for n in out.split() if any(n.startswith(p) for p in prefixes)]
    if names:
        subprocess.run(["docker", "rm", "-f", *names], capture_output=True, env=_docker_env())
    return names


# PIDs of harbor runs in flight, so a SIGTERM/SIGINT handler can stop them (pipeline.py).
CHILDREN: set[int] = set()


def harbor_run(task_dir: str, job_name: str, args: list[str],
               timeout: int = HARBOR_RUN_TIMEOUT_SEC, stop_when=None, on_start=None) -> tuple[str, str]:
    """Run `harbor run` on one task into JOBS_DIR/<job_name>; return (cli output, job dir).
    Shared by the oracle/nop checks and the band eval. If `stop_when(job_dir)` turns true
    while it runs (polled every 15 s), the job is stopped early and the containers of its
    unfinished trials are removed."""
    cmd = [HARBOR, "run", "-p", task_dir, "-o", JOBS_DIR, "--job-name", job_name, "-q", "-y", *args]
    job_dir = os.path.join(JOBS_DIR, job_name)
    started = time.time()
    os.makedirs(JOBS_DIR, exist_ok=True)
    with open(os.path.join(JOBS_DIR, f".{job_name}.cli.txt"), "w+", encoding="utf-8") as out:
        proc = subprocess.Popen(cmd, env=_docker_env(), stdout=out, stderr=subprocess.STDOUT, text=True)
        CHILDREN.add(proc.pid)
        if on_start:  # e.g. the batch ledger records the pid, to kill a stale job on resume
            on_start(proc.pid)
        note = ""
        while proc.poll() is None:
            time.sleep(15 if stop_when else 2)
            if time.time() - started > timeout:
                note = f"\nharbor run timed out after {timeout}s"
            elif stop_when and stop_when(job_dir):
                note = "\nstopped early: verdict already certain"
            else:
                continue
            kill_tree(proc.pid)
            unfinished = [os.path.basename(os.path.dirname(t)) for t in
                          glob.glob(os.path.join(job_dir, "*", "config.json"))
                          if not os.path.exists(os.path.join(os.path.dirname(t), "result.json"))]
            remove_containers(unfinished)
            break
        CHILDREN.discard(proc.pid)
        out.seek(0)
        cli_out = out.read() + note
    cleanup_job(job_dir)
    return cli_out, job_dir


def cleanup_job(job_dir: str) -> list[str]:
    """Harbor can leave a trial's egress sidecar (and its network) running after grading; a
    batch of these exhausts Docker's address pool. Remove whatever is left of this job's trials
    and prune networks nothing is attached to."""
    trials = [os.path.basename(os.path.dirname(c)) for c in glob.glob(os.path.join(job_dir, "*", "config.json"))]
    names = remove_containers(trials)
    subprocess.run(["docker", "network", "prune", "-f"], capture_output=True, env=_docker_env())
    return names


def _phase_seconds(trial: dict) -> dict:
    """Seconds spent solving (agent or oracle) and verifying, from the trial's phase timestamps."""
    from datetime import datetime
    out = {}
    for phase, key in (("agent_execution", "agent_sec"), ("verifier", "verifier_sec")):
        p = trial.get(phase) or {}
        try:
            a, b = (datetime.fromisoformat(str(p[k]).replace("Z", "+00:00")) for k in ("started_at", "finished_at"))
            out[key] = round((b - a).total_seconds(), 1)
        except (KeyError, ValueError, TypeError):
            pass
    return out


def run_harbor(task_dir: str, agent: str, job_name: str) -> CheckResult:
    """Run one oracle/nop trial and return its reward plus failure context."""
    started = time.time()
    args = ["-a", agent]
    if agent == "oracle":
        args += ["--agent-timeout-multiplier", ORACLE_TIMEOUT_MULTIPLIER]
    cli_out, job_dir = harbor_run(task_dir, job_name, args)
    result = CheckResult(name=agent, passed=False, job_dir=job_dir)

    trial_results = glob.glob(os.path.join(job_dir, "*", "result.json"))
    if not trial_results:
        result.error = f"`harbor run -a {agent}` produced no trial result.\n" + _tail(cli_out)
        result.seconds = round(time.time() - started, 1)
        return result

    trial_dir = os.path.dirname(trial_results[0])
    trial = json.loads(_read(trial_results[0]) or "{}")
    rewards = (trial.get("verifier_result") or {}).get("rewards") or {}
    result.reward = rewards.get("reward")
    exc = trial.get("exception_info")
    test_out = _read(os.path.join(trial_dir, "verifier", "test-stdout.txt"))
    agent_out = _read(os.path.join(trial_dir, "agent", "oracle.txt")) if agent == "oracle" else ""
    result.details = {"trial_dir": trial_dir, "exception": exc, **_phase_seconds(trial)}

    expected = 1.0 if agent == "oracle" else 0.0
    result.passed = exc is None and result.reward is not None and float(result.reward) == expected

    if not result.passed:
        parts = []
        if agent == "oracle":
            parts.append(f"Oracle check failed: running solution/solve.sh then the tests gave reward "
                         f"{result.reward} (expected 1).")
        else:
            parts.append("Nop check failed: the tests PASS on the unsolved environment (reward "
                         f"{result.reward}, expected 0). The tests don't check the required change, "
                         "or the environment does not start in the broken state.")
        if exc:
            parts.append("Exception during the trial (build, setup or run):\n"
                         + _tail(json.dumps(exc, indent=1), 4000))
        if agent_out:
            parts.append("solve.sh output (tail):\n" + _tail(agent_out, 3000))
        if test_out:
            parts.append("Verifier / pytest output:\n" + _pytest_excerpt(test_out))
        result.error = "\n\n".join(parts)
    result.seconds = round(time.time() - started, 1)
    return result


def run_all(task_dir: str, job_prefix: str) -> list[CheckResult]:
    """Run checks in order, stopping at the first failure."""
    results = [run_validator(task_dir)]
    if not results[-1].passed:
        return results
    for agent in ("oracle", "nop"):
        results.append(run_harbor(task_dir, agent, f"{job_prefix}-{agent}"))
        if not results[-1].passed:
            break
    return results
