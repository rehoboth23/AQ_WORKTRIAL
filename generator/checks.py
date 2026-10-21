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


def run_harbor(task_dir: str, agent: str, job_name: str) -> CheckResult:
    """Run one oracle/nop trial and return its reward plus failure context."""
    started = time.time()
    env = dict(os.environ)
    env["PATH"] = os.path.expanduser("~/.docker/bin") + os.pathsep + env.get("PATH", "")
    cmd = [HARBOR, "run", "-p", task_dir, "-a", agent, "-o", JOBS_DIR, "--job-name", job_name, "-q", "-y"]
    if agent == "oracle":
        cmd += ["--agent-timeout-multiplier", ORACLE_TIMEOUT_MULTIPLIER]
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=HARBOR_RUN_TIMEOUT_SEC)
        cli_out = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as e:
        cli_out = f"harbor run timed out after {HARBOR_RUN_TIMEOUT_SEC}s\n{e.stdout or ''}"
    job_dir = os.path.join(JOBS_DIR, job_name)
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
    result.details = {"trial_dir": trial_dir, "exception": exc}

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
