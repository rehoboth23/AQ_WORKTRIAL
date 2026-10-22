"""
Live status dashboard: renders what the pipeline is doing to jobs/dashboard.html (gitignored).
The page reloads itself; scripts/dashboard.sh re-renders it every few seconds. Read-only: it
only looks at processes, Docker, and the logs the pipeline already writes.

    python status.py            # render once
"""

import glob
import html
import json
import os
import re
import subprocess
import time

from config import CALIBRATION_FILE, JOBS_DIR, LOGS_DIR, load_difficulty

OUT = os.path.join(JOBS_DIR, "dashboard.html")
# Optional focus: show only processes, runs, jobs and containers whose name or path contains
# this text (e.g. DASHBOARD_ONLY=ledger-goal while watching one experiment). Unset = everything.
ONLY = os.environ.get("DASHBOARD_ONLY", "")


def _pid_alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def _keep(text: str) -> bool:
    return not ONLY or ONLY.lower() in str(text).lower()
RECENT_SEC = 3 * 3600   # runs touched in the last 3 hours count as "recent"
ACTIVE_SEC = 15 * 60    # touched in the last 15 minutes and a process is alive: "active"


def _sh(cmd: list[str]) -> str:
    env = dict(os.environ, PATH=os.path.expanduser("~/.docker/bin") + os.pathsep + os.environ.get("PATH", ""))
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10, env=env).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _jsonl(path: str) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _age(ts: float) -> str:
    s = int(time.time() - ts)
    return f"{s}s" if s < 90 else f"{s // 60}m" if s < 5400 else f"{s // 3600}h{(s % 3600) // 60:02d}m"


def processes() -> list[tuple[str, str, str]]:
    rows = []
    for line in _sh(["ps", "-ww", "-eo", "pid,etime,args"]).splitlines()[1:]:
        pid, etime, args = (line.strip().split(None, 2) + ["", ""])[:3]
        what = None
        if "pipeline.py" in args:
            what = "pipeline (" + ("smoke" if "--smoke" in args else "eval-only" if "--eval-only" in args
                                   else "control" if "--control" in args else "generate + eval") + ")"
        elif "generate.py" in args:
            what = "generate one task"
        elif "from_mutants" in args:
            what = "experiment (mutation check -> band eval)"
        elif "harbor run" in args or "/harbor run" in args:
            agent = args.split(" -a ")[1].split()[0] if " -a " in args else "?"
            what = f"harbor run ({agent})"
        if what and _keep(args):
            rows.append((pid, etime, what, args))
    return rows


def _arg(args: str, flag: str) -> str:
    parts = args.split()
    return parts[parts.index(flag) + 1] if flag in parts and parts.index(flag) + 1 < len(parts) else ""


def describe(what: str, args: str, rs: list[dict]) -> str:
    """What a process is working on: topic/task and stage for a pipeline, task and check type
    for a harbor run."""
    if what.startswith("pipeline"):
        topic = ""
        tfile = _arg(args, "--topics")
        if tfile and os.path.exists(tfile):
            with open(tfile, encoding="utf-8") as f:
                topic = f.readline().strip()
        if not topic:
            return _arg(args, "--batch-id") or " ".join(args.split()[2:])[:80]
        run = next((r for r in rs if r["topic"] == topic), None)
        name, stage = "", ""
        if run:
            stage = run["stage"]
            sp = os.path.join(run["dir"], "spec.json")
            if os.path.exists(sp):
                try:
                    name = json.load(open(sp)).get("name", "")
                except (json.JSONDecodeError, OSError):
                    pass
        return (f"topic: {topic[:70]}" + (f" | task: {name}" if name else "")
                + (f" | stage: {stage}" if stage else ""))
    if what.startswith("harbor run"):
        task = os.path.basename(_arg(args, "-p").rstrip("/"))
        job = _arg(args, "--job-name")
        kind = ("band eval (5 agent runs)" if job.startswith("band-") else
                "oracle check (reference solution)" if job.endswith("-oracle") else
                "nop check (untouched container)" if job.endswith("-nop") else job)
        return f"task: {task} | {kind}"
    return ""


def containers() -> list[list[str]]:
    out = _sh(["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"])
    return [l.split("\t") for l in out.splitlines() if l.strip() and _keep(l.split("\t")[0])]


def stage_of(events: list[dict]) -> str:
    """Human-readable current stage of one generation/batch run from its events."""
    if not events:
        return "starting"
    e = events[-1]
    kind = e.get("event")
    if kind == "finish":
        return f"finished: {e.get('status')}"
    if kind == "band_done":
        return f"band eval done: {e.get('verdict')} ({e.get('passes')}/5) -> {e.get('decision')}"
    if kind == "band_start":
        return f"band eval running ({e.get('task')})"
    if kind == "band_job":
        return f"band job done: {e.get('outcomes')}"
    if kind == "checks":
        return f"checks round {e.get('round')}: {e.get('results')} " + ("passed" if e.get("passed") else "failed")
    if kind == "llm_call":
        nxt = {"spec": "critic or files", "critic": "files", "files": "checks (Docker)"}.get(
            str(e.get("label")).split("-")[0], "next step")
        return f"{e.get('label')} done ({e.get('seconds')}s); now: {nxt}"
    if kind == "spec_gate":
        return "spec gate: " + ("passed" if not e.get("problems") else f"{len(e['problems'])} problems, re-spec")
    if kind == "critic":
        return "critic reviewed spec; now: files"
    if kind == "start":
        return "spec (glm-5.1 designing)" + (" [control]" if e.get("control") else "")
    if kind == "llm_start":
        return f"{_desc(str(e.get('label')))} (in progress)"
    if kind == "critic_error":
        return "critic failed; continuing with the gated spec"
    return kind or "?"


def runs() -> list[dict]:
    out = []
    for d in glob.glob(os.path.join(LOGS_DIR, "*", "events.jsonl")):
        if not _keep(d):
            continue
        mtime = os.path.getmtime(d)
        if time.time() - mtime > RECENT_SEC:
            continue
        ev = _jsonl(d)
        name = os.path.basename(os.path.dirname(d))
        topic = next((e.get("topic") for e in ev if e.get("event") == "start"), "")
        out.append({"name": name, "topic": topic or "", "stage": stage_of(ev), "mtime": mtime,
                    "events": ev, "dir": os.path.dirname(d)})
    return sorted(out, key=lambda r: -r["mtime"])


LABEL_DESC = {"spec": "designing the task (spec)", "critic": "red-teaming the design (critic)",
              "project": "writing the project files (manifest first)",
              "files": "writing instruction, Dockerfile, solve.sh and tests",
              "repair": "repairing files after a failed check",
              "review": "checking instruction.md for diagnosis leaks",
              "triage": "judging whose fault a failed eval run was"}


STAGE = {"spec": "1 design", "spec-a": "1b redesign", "critic": "2 critic", "project": "3a writing project",
         "files": "3c writing core files",
         "repair": "4 repair", "review": "3b instruction review", "checks": "5 Docker checks", "band": "6 band eval", "triage": "7 triage"}


def _stage(label: str) -> str:
    if label.startswith("spec-a"):
        return STAGE["spec-a"]
    return STAGE.get(label.split("-")[0], label)


def _desc(label: str) -> str:
    if label.startswith("spec-a"):
        return "re-designing after the spec gate rejected the design"
    return LABEL_DESC.get(label.split("-")[0], label)


def _etime_sec(etime: str) -> int:
    """ps etime ([[dd-]hh:]mm:ss) -> seconds."""
    days, _, rest = etime.rpartition("-")
    parts = [int(x) for x in rest.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return (int(days) if days else 0) * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]


def oldest_pipeline_start(procs) -> float | None:
    ages = [_etime_sec(t) for _, t, w, _a in procs if w.startswith(("pipeline", "generate", "experiment"))]
    return time.time() - max(ages) - 5 if ages else None


def generator_activity(rs: list[dict], alive_since: float | None) -> list[tuple[str, str, str, str]]:
    """What glm-5.1 is doing per run: an in-flight call (exact, from llm_start events) or,
    for runs started before those events existed, the step implied by the last finished one."""
    rows = []
    for r in rs:
        ev = r["events"]
        if not ev or ev[-1].get("event") in ("finish", "band_done") or alive_since is None:
            continue
        # A resumed run (pipeline --resume) appends to an older logs dir: its latest start or
        # resume event is when the current process picked it up, not its first event.
        began = next((e for e in reversed(ev) if e.get("event") in ("start", "resume")), ev[0])
        if began.get("pid"):  # runs that record their process: live only while it is
            if not _pid_alive(began["pid"]):
                continue
        else:  # older runs: began before any live pipeline process means dead
            started = time.mktime(time.strptime(began["time"], "%Y-%m-%dT%H:%M:%S"))
            if started < alive_since:
                continue
        done = {(e.get("label"), e.get("attempt")) for e in ev if e.get("event") == "llm_call"}
        flight = [e for e in ev if e.get("event") == "llm_start" and (e.get("label"), e.get("attempt")) not in done]
        last = ev[-1]
        since = time.mktime(time.strptime(last["time"], "%Y-%m-%dT%H:%M:%S"))
        attempt = "-"
        if flight:
            f = flight[-1]
            since = time.mktime(time.strptime(f["time"], "%Y-%m-%dT%H:%M:%S"))
            stage, doing = _stage(f["label"]), _desc(f["label"])
            attempt = str(f.get("attempt", 0) + 1)
        elif last.get("event") == "start":
            stage, doing = STAGE["spec"], "designing the task (spec) [inferred]"
        elif last.get("event") == "llm_call" and str(last.get("label")).startswith("spec"):
            stage, doing = STAGE["critic"], "red-teaming the design or writing files [inferred]"
        elif last.get("event") in ("critic", "spec_gate", "critic_error"):
            stage, doing = STAGE["files"], "writing the task files [inferred]"
        elif last.get("event") == "llm_call" and str(last.get("label")).startswith(("files", "repair")):
            stage, doing = STAGE["checks"], "idle: Docker checks running (validator, oracle, nop)"
        elif last.get("event") == "checks" and not last.get("passed"):
            stage, doing = STAGE["repair"], "repairing files after a failed check [inferred]"
        elif last.get("event") in ("band_start", "band_job"):
            stage, doing = STAGE["band"], "idle: glm-5.3-flash band eval running"
        else:
            continue
        design = ""
        spec_path = os.path.join(r["dir"], "spec.json")
        if os.path.exists(spec_path):
            try:
                sp = json.load(open(spec_path))
                layers = sorted({str(x.get("layer")) for x in sp.get("faults") or [] if isinstance(x, dict)})
                rules = sp.get("requirements") or []
                themes = sorted({str(r.get("theme")) for r in rules if isinstance(r, dict)})
                design = (f"{sp.get('name')}: {sp.get('challenge_kind') or 'no challenge kind'}, "
                          + (f"{len(rules)} rules over {len(themes)} themes" if rules
                             else f"{len(sp.get('faults') or [])} faults in {layers or '-'}"))
            except (json.JSONDecodeError, OSError):
                pass
        # Every model call this run has made, across all stages (each attempt logs a start;
        # runs from before start-logging only have finished calls).
        starts = [x for x in ev if x.get("event") == "llm_start"]
        calls = starts or [x for x in ev if x.get("event") == "llm_call"]
        retries = sum(1 for x in calls if (x.get("attempt") or 0) > 0)
        total = f"{len(calls)}" + (f" ({retries} retr{'y' if retries == 1 else 'ies'})" if retries else "")
        rows.append((r["topic"][:55] or r["name"], stage, attempt, total, doing, _age(since), design))
    return rows


def turn_pattern(steps) -> str:
    """One letter per agent turn: r=read, E=edit, B=build/run, -=no command."""
    out = []
    for s in steps:
        k = " ".join(str((c.get("arguments") or {}).get("keystrokes", "")) for c in (s.get("tool_calls") or []))
        if re.search(r"apply_patch|python3? - <<|cat > |sed -i|perl -pi|\.write\(|patch ", k):
            out.append("E")
        elif "build.py" in k or "make " in k:
            out.append("B")
        elif not k.strip():
            out.append("-")
        else:
            out.append("r")
    return "".join(out)


def phase_of(pattern: str) -> str:
    """Rough phase from the last 8 turns."""
    tail = pattern[-8:]
    if not tail:
        return "starting"
    edits, reads = tail.count("E") + tail.count("B"), tail.count("r")
    if edits >= 6:
        return "fixing/testing"
    if edits >= 3:
        return "fixing"
    return "reading/diagnosing" if reads >= 5 else "mixed"


def live_trials() -> set[str]:
    """Lower-cased trial names whose Docker container is running (the source of truth: a trial
    stopped by killing its job has no result.json but also no container)."""
    names = _sh(["docker", "ps", "--format", "{{.Names}}"]).split()
    return {n.split("__env")[0] for n in names if "__env" in n}


def eval_activity(limit: int = 6) -> list[tuple[str, str, str]]:
    """What glm-5.3-flash is doing in each running band-eval trial: its latest analysis."""
    rows = []
    live = live_trials()
    # Any job with agent trajectories (band evals and ad-hoc experiments), not just "band-*".
    for tj in glob.glob(os.path.join(JOBS_DIR, "*", "*", "agent", "trajectory.json")):
        trial = os.path.dirname(os.path.dirname(tj))
        if not _keep(trial):
            continue
        if os.path.exists(os.path.join(trial, "result.json")) or os.path.basename(trial).lower() not in live:
            continue
        try:
            steps = [s for s in json.load(open(tj)).get("steps", []) if s.get("source") == "agent"]
        except (json.JSONDecodeError, OSError):
            continue
        msg = steps[-1].get("message") if steps else ""
        msg = msg if isinstance(msg, str) else json.dumps(msg)
        cmds = " ; ".join(str((c.get("arguments") or {}).get("keystrokes", "")).strip()
                          for c in (steps[-1].get("tool_calls") or []) if isinstance(c, dict)) if steps else ""
        job = os.path.basename(os.path.dirname(trial))
        pat = turn_pattern(steps)
        rows.append((f"{job[:28]} / {os.path.basename(trial)[-7:]}",
                     f"{len(steps)} turns, last {_age(os.path.getmtime(tj))} ago · {phase_of(pat)}"
                     f"<br><code>{pat[-40:]}</code>",
                     " ".join(msg.split())[:260], " ".join(cmds.split())[:160]))
    return rows[:limit]


def band_jobs() -> list[dict]:
    out = []
    live = live_trials()
    for jd in glob.glob(os.path.join(JOBS_DIR, "*")):
        if not _keep(jd):
            continue
        if not os.path.isdir(jd) or not (os.path.basename(jd).startswith("band-")
                                         or glob.glob(os.path.join(jd, "*", "agent", "trajectory.json"))):
            continue
        if time.time() - os.path.getmtime(jd) > RECENT_SEC:
            continue
        trials = []
        for td in sorted(glob.glob(os.path.join(jd, "*", ""))):
            res = os.path.join(td, "result.json")
            if os.path.exists(res):
                try:
                    r = json.load(open(res, encoding="utf-8"))
                except json.JSONDecodeError:
                    trials.append("?")
                    continue
                exc = (r.get("exception_info") or {}).get("exception_type")
                rew = ((r.get("verifier_result") or {}).get("rewards") or {}).get("reward")
                trials.append(f"invalid ({exc})" if exc else "pass" if rew == 1.0 else "fail")
            else:
                steps = 0
                tj = os.path.join(td, "agent", "trajectory.json")
                if os.path.exists(tj):
                    try:
                        steps = sum(1 for s in json.load(open(tj)).get("steps", []) if s.get("source") == "agent")
                    except (json.JSONDecodeError, OSError):
                        pass
                alive = os.path.basename(os.path.dirname(td)).lower() in live
                trials.append(f"running ({steps} steps)" if alive else f"stopped ({steps} steps)")
        out.append({"job": os.path.basename(jd), "trials": trials, "mtime": os.path.getmtime(jd)})
    return sorted(out, key=lambda r: -r["mtime"])


def render() -> str:
    cfg = load_difficulty()
    procs, conts, rs, bands = processes(), containers(), runs(), band_jobs()
    calib = [r for r in _jsonl(CALIBRATION_FILE) if r.get("verdict")][-8:]
    today = time.strftime("%Y-%m-%d")
    eval_cost = sum(r.get("cost_usd") or 0 for r in _jsonl(CALIBRATION_FILE) if str(r.get("time", "")).startswith(today))
    gen_tokens = 0
    for p in glob.glob(os.path.join(LOGS_DIR, "*", "summary.json")):
        if time.time() - os.path.getmtime(p) < 86400:
            try:
                t = json.load(open(p)).get("tokens") or {}
                gen_tokens += (t.get("prompt_tokens") or 0) + (t.get("completion_tokens") or 0)
            except (json.JSONDecodeError, OSError):
                pass
    busy = bool(procs or conts)
    for r in rs:  # an unfinished run with nothing alive (or untouched for long) was stopped/killed
        done = r["stage"].startswith(("finished", "band eval done", "band job done"))
        if not done and (not procs or time.time() - r["mtime"] > ACTIVE_SEC * 4):
            r["stage"] = "stopped (no process running) — last: " + r["stage"]
    e = html.escape

    def table(head, rows):
        if not rows:
            return '<p class="muted">none</p>'
        return ("<table><tr>" + "".join(f"<th>{e(h)}</th>" for h in head) + "</tr>"
                + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</table>")

    def chip(t):
        cls = "ok" if t.startswith("pass") else "bad" if t.startswith(("fail", "invalid", "stopped")) else "run"
        return f'<span class="chip {cls}">{e(t)}</span>'

    gen_rows = generator_activity(rs, oldest_pipeline_start(procs))
    ev_rows = eval_activity()
    sections = [
        f'<h2>Now {"<span class=chip run>busy</span>" if busy else "<span class=chip ok>idle</span>"}</h2>',
        table(["pid", "running for", "what", "working on"],
              [(e(p), e(t), e(w), e(describe(w, a, rs))) for p, t, w, a in procs]),
        "<h2>GLM activity</h2>",
        "<p class=muted>glm-5.1 (task author) per run. [inferred] = run started before live call logging; "
        "stage implied by its last finished step.</p>",
        table(["run / topic", "stage", "attempt", "total attempts", "glm-5.1 is…", "for", "current design"],
              [(e(a), "<b>" + e(st.split(" ", 1)[-1]) + "</b>", e(at), e(tot), e(b), e(c), e(d))
               for a, st, at, tot, b, c, d in gen_rows]),
        "<p class=muted>glm-5.3-flash (agent under test), running agent trials (band evals and experiments): latest turn</p>",
        "<p class=muted>turn letters: r = read, E = edit, B = build/run, - = no command</p>",
        table(["job / trial", "progress", "agent's latest analysis", "latest commands"],
              [(e(a), b, e(c), "<code>" + e(d) + "</code>") for a, b, c, d in ev_rows]),
        "<h2>Docker containers</h2>", table(["container", "status"], [(e(n), e(s)) for n, s in conts]),
        "<h2>Runs (last 3 h)</h2>",
        table(["run", "topic", "current stage", "updated"],
              [(e(r["name"]), e(r["topic"][:70]), ("<b>" if time.time() - r["mtime"] < ACTIVE_SEC and busy else "")
                + e(r["stage"]), e(_age(r["mtime"]) + " ago")) for r in rs[:12]]),
        "<h2>Agent evals (band evals and experiments, last 3 h)</h2>",
        table(["job", "runs"], [(e(b["job"]), " ".join(chip(t) for t in b["trials"])) for b in bands[:8]]),
        "<h2>Difficulty knobs</h2>",
        table(["knob", "value"], [(e(k), e(str(v))) for k, v in {**cfg["knobs"], **{f"discovery.{k}": v for k, v in cfg["discovery"].items()}}.items()]),
        "<h2>Recent verdicts</h2>",
        table(["time", "task", "verdict", "passes", "note"],
              [(e(str(r.get("time", ""))[11:19]), e(str(r.get("name"))[:45]),
                e(str(r.get("verdict"))), e(str(r.get("passes"))), e(str(r.get("note", ""))[:90])) for r in calib]),
        f'<p class="muted">Today: eval cost ${eval_cost:.3f} · generation tokens (24 h) {gen_tokens:,}</p>',
    ]
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="10">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Pipeline status</title>
<style>
:root{{--bg:#fafafa;--fg:#1d1d1f;--muted:#6e6e73;--line:#e3e3e8;--ok:#1a7f37;--bad:#c62828;--run:#0b62d6}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151517;--fg:#eee;--muted:#9a9aa0;--line:#2c2c30;--ok:#3fb950;--bad:#f85149;--run:#58a6ff}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.45 -apple-system,system-ui,sans-serif;margin:0;padding:16px;max-width:1100px}}
h1{{font-size:20px;margin:0 0 4px}} h2{{font-size:15px;margin:22px 0 6px}}
table{{border-collapse:collapse;width:100%;display:block;overflow-x:auto}} th,td{{text-align:left;padding:4px 8px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{color:var(--muted);font-weight:600}} .muted{{color:var(--muted)}}
.chip{{display:inline-block;padding:1px 7px;margin:1px;border-radius:9px;font-size:12px;border:1px solid currentColor}}
.ok{{color:var(--ok)}} .bad{{color:var(--bad)}} .run{{color:var(--run)}}
</style></head><body>
<h1>Pipeline status</h1><p class="muted">Updated {time.strftime("%H:%M:%S")} · page reloads every 10 s</p>
{"".join(sections)}
</body></html>"""


def main() -> None:
    os.makedirs(JOBS_DIR, exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(render())
    os.replace(tmp, OUT)


if __name__ == "__main__":
    main()
