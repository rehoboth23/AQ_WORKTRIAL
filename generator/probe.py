"""
Knowledge probe and difficulty dial (domain genre).

A domain task is solved only if the agent gets every knowledge point right, and its own tests
share its misunderstandings, so the pass rate is roughly the product of the per-point rates at
which the EVAL model knows each detail. Measuring those rates costs a few cheap calls, instead
of guessing and paying for a full generation and band eval to find out.

    rates = probe_points(points)           # [{"rate": 0.6, "answers": [...]}, ...]
    predicted_pass(rates)                   # e.g. 0.8 * 0.6 * 1.0 * 0.6 = 0.29
"""

import math
import re
from concurrent.futures import ThreadPoolExecutor

import llm
from config import PROBE_MODEL, PROBE_RUNS

PROBE_SYSTEM = """\
Answer the question. Reply with ONLY the final answer on the last line, exactly in the form the
question asks for (a number, a hex string, a date, a word), with no explanation after it."""


def _norm(s: str) -> str:
    s = s.strip().strip("`*").strip().rstrip(".").lower()
    return re.sub(r"\s+", " ", s)


def grade(reply: str, answer: str) -> bool:
    """The last non-empty line of the reply equals the expected answer (alternatives separated
    by '||'), ignoring case, surrounding backticks and a trailing period."""
    lines = [l for l in (reply or "").splitlines() if l.strip()]
    if not lines:
        return False
    got = _norm(re.sub(r"(?i)^\s*(final answer|answer)\s*[:=]\s*", "", lines[-1]))
    return any(got == _norm(a) for a in str(answer).split("||"))


def _ask(question: str, log=None, label="probe") -> str:
    try:
        text, _ = llm.chat(PROBE_SYSTEM, question, lambda t: t, log, label, model=PROBE_MODEL)[:2]
        return text
    except llm.LLMError:
        return ""


def probe_points(points: list[dict], runs: int = PROBE_RUNS, log=None) -> list[dict]:
    """Ask each point's probe_question `runs` times (all calls in parallel); return its rate."""
    jobs = [(i, k) for i, p in enumerate(points) if p.get("probe_question") for k in range(runs)]
    with ThreadPoolExecutor(max_workers=min(16, max(1, len(jobs)))) as ex:
        replies = list(ex.map(lambda j: _ask(points[j[0]]["probe_question"], log, f"probe-{j[0]}-{j[1]}"), jobs))
    out = [{"rate": None, "answers": []} for _ in points]
    for (i, _), reply in zip(jobs, replies):
        out[i]["answers"].append(((reply or "").strip().splitlines() or [""])[-1][:80])
        out[i].setdefault("hits", 0)
        out[i]["hits"] += grade(reply, points[i].get("probe_answer", ""))
    for o in out:
        if o["answers"]:
            o["rate"] = o["hits"] / len(o["answers"])
    return out


def predicted_pass(results: list[dict]) -> float:
    """Chance that every probed point is right in one run (independent points)."""
    rates = [r["rate"] for r in results if r.get("rate") is not None]
    return math.prod(rates) if rates else 1.0
