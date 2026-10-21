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
import json
import os
import posixpath
import re
import shutil
import sys
import time

import toml
from pydantic import BaseModel, Field

import prompts
from checks import run_all
from config import CANARY_LINE, LOGS_DIR, MAX_REPAIR_ROUNDS, MODEL, OUTPUT_DIR, TASK_ORG
from llm import LLMError, chat, parse_file_blocks, parse_json_object

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
  pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA

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


def slugify(text: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "task"


def parse_spec(text: str) -> dict:
    spec = Spec.model_validate(parse_json_object(text)).model_dump()
    spec["name"] = slugify(spec["name"], 40)
    if spec["difficulty"] not in ("easy", "medium", "hard"):
        spec["difficulty"] = "hard"
    return spec


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
        "agent": {"timeout_sec": 3600.0},
        "environment": {
            "build_timeout_sec": 600.0,
            "cpus": 1,
            "memory_mb": 2048,
            "storage_mb": 10240,
        },
    })


def write_task(task_dir: str, spec: dict, task_name: str, files: dict[str, str]) -> None:
    """(Re)write the whole task directory from the model's files plus our boilerplate."""
    if os.path.isdir(task_dir):
        shutil.rmtree(task_dir)
    out = dict(files)
    for path in ("environment/Dockerfile", "solution/solve.sh", "tests/test_outputs.py"):
        out[path] = _with_canary(out[path])
    out["tests/test.sh"] = TEST_SH
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
        self.n = 0
        self.tokens = {"prompt_tokens": 0, "completion_tokens": 0}

    def event(self, kind: str, **data) -> None:
        rec = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": kind, **data}
        with open(os.path.join(self.dir, "events.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    def llm(self, label: str, record: dict) -> None:
        self.n += 1
        with open(os.path.join(self.dir, f"{self.n:02d}-{label}.txt"), "w", encoding="utf-8") as f:
            f.write(record.get("raw", ""))
        for k in self.tokens:
            self.tokens[k] += (record.get("usage") or {}).get(k) or 0
        self.event("llm_call", label=label, **{k: v for k, v in record.items() if k != "raw"})

    def write_json(self, name: str, data) -> None:
        with open(os.path.join(self.dir, name), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def generate_task(topic: str, output_dir: str | None = None) -> dict:
    """Generate a Harbor task for the given topic.

    Args:
        topic: A short description of the task to generate
            (e.g. "fix a memory bug in a C ring buffer").
        output_dir: Where to write the generated task files.
            Defaults to output/<task-name from the spec>.

    Returns:
        dict with at least {"task_dir": <path>, "status": "ok" | "failed"}.
    """
    started = time.time()
    run_id = f"{slugify(topic, 40)}-{time.strftime('%Y%m%d-%H%M%S')}"
    log = RunLog(os.path.join(os.path.abspath(LOGS_DIR), run_id))
    log.event("start", topic=topic, model=MODEL)
    summary = {"topic": topic, "run_id": run_id, "logs_dir": log.dir, "task_dir": None,
               "status": "failed", "rounds": []}

    def finish(status: str, **extra) -> dict:
        summary.update(status=status, tokens=log.tokens, seconds=round(time.time() - started, 1), **extra)
        log.event("finish", status=status)
        log.write_json("summary.json", summary)
        return summary

    try:
        spec, _, _ = chat(prompts.SPEC_SYSTEM, prompts.spec_user(topic), parse_spec, log.llm, "spec")
        log.write_json("spec.json", spec)
        raw, _, _ = chat(prompts.FILES_SYSTEM, prompts.files_user(spec), parse_file_blocks, log.llm, "files")
    except LLMError as e:
        return finish("failed", error=str(e))

    task_name = spec["name"]
    task_dir = os.path.abspath(output_dir or os.path.join(OUTPUT_DIR, task_name))
    if output_dir is None and os.path.exists(task_dir):  # never overwrite an earlier task
        task_dir = f"{task_dir}-{time.strftime('%H%M%S')}"
        task_name = os.path.basename(task_dir)
    files, dropped = clean_files(raw)

    for rnd in range(MAX_REPAIR_ROUNDS + 1):
        record = {"round": rnd, "dropped_paths": dropped, "checks": []}
        missing = missing_files(files)
        if missing:
            error = "These required files are missing or empty: " + ", ".join(missing)
        else:
            write_task(task_dir, spec, task_name, files)
            results = run_all(task_dir, f"gen-{run_id}-r{rnd}")
            record["checks"] = [r.to_dict() for r in results]
            error = next((r.error for r in results if not r.passed), "")
        summary["rounds"].append(record)
        log.event("checks", round=rnd, passed=not error,
                  results={c["name"]: c["reward"] if c["name"] != "validator" else c["passed"]
                           for c in record["checks"]})
        if not error:
            summary["task_dir"] = task_dir
            return finish("ok", task_name=f"{TASK_ORG}/{task_name}")
        if rnd == MAX_REPAIR_ROUNDS:
            break
        try:
            patch, _, _ = chat(prompts.REPAIR_SYSTEM, prompts.repair_user(spec, files, error),
                               parse_file_blocks, log.llm, f"repair-r{rnd + 1}")
        except LLMError as e:
            summary["error"] = str(e)
            break
        fixed, dropped = clean_files(patch)
        files.update(fixed)

    # Failed: keep the last attempt in the logs, not in output/, so output/ only holds good tasks.
    if os.path.isdir(task_dir):
        shutil.move(task_dir, os.path.join(log.dir, "last-attempt"))
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
