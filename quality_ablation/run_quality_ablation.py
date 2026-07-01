"""
MARBLE QUALITY / CORRECTNESS ablation — same-model, all 4 conditions x 4 domains.

Motivation
----------
The headline MARBLE ablation number in the blog is a COMPLETION metric (did the
team produce an artifact within the timeout). This script layers MARBLE's own
QUALITY signal on top of the *identical* same-model transcripts so the
coordination delta can be read as a quality/correctness effect, not just
"work finished".

Two metrics per (condition, domain, task):

  1. MILESTONE-KPI  (uniform across all 4 domains — the primary metric)
     Faithful to MARBLE's milestone approach:
       * GOLD milestones are generated ONCE per task from the task description
         (shared across all conditions -> identical yard-stick).
       * For each condition's output the judge marks each gold milestone
         achieved / not-achieved based ONLY on that output.
       * KPI rate = achieved / total gold milestones.
     Because the gold set is shared and the judge/prompt/model are identical for
     every condition, the between-condition delta is a valid relative measure
     even if the judge is imperfect (symmetric bias cancels in the delta).

  2. CODING RUBRIC (1-5 correctness/completeness/quality) — fills the gap where
     coding only had a "quality_estimate" placeholder. Research & bargaining
     already have real per-task rubric scores (gpt-4o judged); database has the
     dedicated root-cause recall metric (judge_results_v2.json). Coding was the
     hole, so we score it here with the same judge for internal consistency.

Judge
-----
No OPENAI/AZURE/ANTHROPIC key is present, so judging goes through the Copilot
CLI (claude-opus-4.6) — the SAME family as the evaluated model. This is a
same-family judge and is disclosed as such. Mitigations: (a) milestone checks
are concrete/objective, (b) the SAME judge is applied uniformly to every
condition so bias is symmetric in the delta, (c) we cross-check the KPI ranking
against the pre-existing gpt-4o rubric scores for research & bargaining.

Resumable: every cell is cached to disk; re-running skips finished cells.
"""
import json
import os
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

PUB = r"C:\Users\tamirdresher\source\repos\squad-marble-benchmark"
QA = os.path.join(PUB, "quality_ablation")
GOLD_DIR = os.path.join(QA, "gold")
CELL_DIR = os.path.join(QA, "cells")
WS_DIR = os.path.join(QA, "judge-ws")

# Task source (prompts) lives in the worktree marble-upstream clone.
MB = (r"C:\Users\tamirdresher\.copilot\repos\copilot-worktrees\tamresearch1"
      r"\tamirdresher-microsoft-fluffy-dollop\squad-marble\marble-upstream\multiagentbench")
DOMAIN_FILE = {
    "coding": "coding/coding_main.jsonl",
    "research": "research/research_main.jsonl",
    "bargaining": "bargaining/bargaining_main.jsonl",
    "database": "database/database_main.jsonl",
}

RESULTS = (r"C:\Users\tamirdresher\.copilot\repos\copilot-worktrees\tamresearch1"
           r"\tamirdresher-microsoft-fluffy-dollop\squad-marble\results")
COND_DIR = {
    "full_squad": "result_squad-copilot-cli",
    "coord_only": "result_coord-only",
    "no_squad": "result_no-squad-expanded",
    "memory_only": "result_memory-only",
}

DOMAINS = ["coding", "research", "bargaining", "database"]
CONDS = ["full_squad", "coord_only", "no_squad", "memory_only"]
TASK_IDS = ["1", "10", "20", "30", "40", "50", "60", "70", "80", "90"]

HEAD, TAIL = 3000, 8000
WORKERS = int(os.environ.get("QA_WORKERS", "4"))

for d in (GOLD_DIR, CELL_DIR, WS_DIR):
    os.makedirs(d, exist_ok=True)


# ---------- data loading -------------------------------------------------
_task_cache = {}


def task_content(domain, tid):
    if domain not in _task_cache:
        rows = {}
        with open(os.path.join(MB, DOMAIN_FILE[domain]), encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    rows[str(r["task_id"])] = r
        _task_cache[domain] = rows
    r = _task_cache[domain][tid]
    return r["task"]["content"], r["task"].get("output_format", "")


def load_output(cond, domain, tid):
    p = os.path.join(RESULTS, COND_DIR[cond], domain, f"task_{tid}.json")
    if not os.path.exists(p):
        return "", "missing"
    try:
        d = json.load(open(p, encoding="utf-8-sig"))
    except Exception:
        return "", "parse_error"
    status = str(d.get("status", "")).lower()
    out = d.get("output") or d.get("final_output") or ""
    if status == "not_run" or not out:
        return "", "no_output"
    if isinstance(out, str) and out.strip().upper().startswith("TIMEOUT"):
        return "", "timeout"
    return out, "ok"


def window(text):
    if len(text) <= HEAD + TAIL:
        return text
    return text[:HEAD] + "\n\n...[middle omitted for length]...\n\n" + text[-TAIL:]


# ---------- judge call ---------------------------------------------------
def judge(prompt, ws):
    os.makedirs(ws, exist_ok=True)
    ansp = os.path.join(ws, "ans.json")
    if os.path.exists(ansp):
        os.remove(ansp)
    cmd = ["copilot", "--yolo", "--autopilot", "--model", "claude-opus-4.6",
           "--session-id", str(uuid.uuid4()), "-p", prompt, "-C", ws]
    env = dict(os.environ)
    env["GH_TOKEN"] = ""
    try:
        subprocess.run(cmd, cwd=ws, timeout=360, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    except subprocess.TimeoutExpired:
        pass
    if os.path.exists(ansp):
        try:
            return json.load(open(ansp, encoding="utf-8-sig"))
        except Exception:
            return None
    return None


# ---------- phase A: gold milestones (shared per task) -------------------
def gen_gold(domain, tid):
    outp = os.path.join(GOLD_DIR, domain, f"task_{tid}.json")
    if os.path.exists(outp):
        return
    content, fmt = task_content(domain, tid)
    prompt = (
        "You are designing an OBJECTIVE evaluation rubric for a multi-agent task. "
        "Read the task below and list the 6 most important CONCRETE, CHECKABLE "
        "milestones that ANY correct solution MUST achieve. Each milestone must be "
        "a specific, verifiable outcome (not a vague quality). Do NOT reference any "
        "particular solution — derive them only from the task requirements.\n\n"
        f"=== TASK ({domain}) ===\n{content[:6000]}\n"
        f"=== OUTPUT FORMAT ===\n{fmt[:1500]}\n=== END ===\n\n"
        'Write ans.json in the current directory: '
        '{"milestones": ["m1", "m2", "m3", "m4", "m5", "m6"]}. Nothing else.'
    )
    ws = os.path.join(WS_DIR, "gold", domain, f"t{tid}")
    res = judge(prompt, ws)
    ms = []
    if isinstance(res, dict):
        ms = [str(m) for m in res.get("milestones", []) if str(m).strip()]
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    json.dump({"domain": domain, "task": tid, "milestones": ms},
              open(outp, "w", encoding="utf-8"), indent=2)
    print(f"[gold] {domain:<10} t{tid:<3} -> {len(ms)} milestones", flush=True)


def load_gold(domain, tid):
    p = os.path.join(GOLD_DIR, domain, f"task_{tid}.json")
    return json.load(open(p, encoding="utf-8"))["milestones"]


# ---------- phase B+C: per-cell scoring ---------------------------------
def score_cell(cond, domain, tid):
    outp = os.path.join(CELL_DIR, cond, domain, f"task_{tid}.json")
    if os.path.exists(outp):
        return
    content, _ = task_content(domain, tid)
    gold = load_gold(domain, tid)
    text, status = load_output(cond, domain, tid)

    cell = {"cond": cond, "domain": domain, "task": tid, "status": status,
            "raw_len": len(text), "n_gold": len(gold)}

    if not text or not gold:
        # genuinely produced nothing -> 0 milestones achieved
        cell["kpi_achieved"] = [False] * len(gold)
        cell["kpi_rate"] = 0.0
        if domain == "coding":
            cell["rubric"] = {"correctness": 1, "completeness": 1, "quality": 1, "avg": 1.0}
        json.dump(cell, _open_w(outp), indent=2)
        print(f"[cell] {cond:<11} {domain:<10} t{tid:<3} EMPTY({status}) kpi=0.0", flush=True)
        return

    win = window(text)

    # --- milestone KPI ---
    gold_lines = "\n".join(f"{i+1}. {m}" for i, m in enumerate(gold))
    kpi_prompt = (
        "You are a strict evaluation judge. Do NOT run commands or investigate. "
        "Below is a TASK, a list of GOLD MILESTONES, and an AGENT OUTPUT. For EACH "
        "gold milestone decide whether the agent output ACHIEVES it, based ONLY on "
        "evidence present in the output. Be strict: partial or merely-mentioned "
        "counts as NOT achieved unless the output actually delivers it. The output "
        "may be a long transcript; the final deliverable is usually near the end.\n\n"
        f"=== TASK ({domain}) ===\n{content[:2500]}\n\n"
        f"=== GOLD MILESTONES ({len(gold)}) ===\n{gold_lines}\n\n"
        f"=== AGENT OUTPUT ===\n{win}\n=== END OUTPUT ===\n\n"
        'Write ans.json: {"achieved": [true/false, ...]} with exactly '
        f"{len(gold)} booleans in milestone order. Nothing else."
    )
    ws = os.path.join(WS_DIR, "kpi", cond, domain, f"t{tid}")
    res = judge(kpi_prompt, ws)
    ach = []
    if isinstance(res, dict) and isinstance(res.get("achieved"), list):
        ach = [bool(x) for x in res["achieved"]][:len(gold)]
    while len(ach) < len(gold):
        ach.append(False)
    cell["kpi_achieved"] = ach
    cell["kpi_rate"] = round(sum(ach) / len(gold), 4) if gold else 0.0

    # --- coding rubric (fills the placeholder gap) ---
    if domain == "coding":
        rub_prompt = (
            "You are a strict code reviewer. Rate the AGENT OUTPUT (a software "
            "solution) against the TASK on three axes, each 1-5 (5=excellent):\n"
            "  correctness  - does the code correctly implement the required behavior?\n"
            "  completeness - are all required features/endpoints/rules present?\n"
            "  quality      - structure, clarity, error handling, tests.\n"
            "Judge ONLY what is in the output. Missing code = low score.\n\n"
            f"=== TASK ===\n{content[:2500]}\n\n"
            f"=== AGENT OUTPUT ===\n{win}\n=== END ===\n\n"
            'Write ans.json: {"correctness":N,"completeness":N,"quality":N}. Nothing else.'
        )
        ws2 = os.path.join(WS_DIR, "rubric", cond, domain, f"t{tid}")
        r2 = judge(rub_prompt, ws2)
        if isinstance(r2, dict):
            try:
                c = int(r2.get("correctness", 3)); cm = int(r2.get("completeness", 3)); q = int(r2.get("quality", 3))
                c, cm, q = [max(1, min(5, v)) for v in (c, cm, q)]
                cell["rubric"] = {"correctness": c, "completeness": cm, "quality": q,
                                  "avg": round((c + cm + q) / 3, 2)}
            except Exception:
                cell["rubric"] = None
        else:
            cell["rubric"] = None

    json.dump(cell, _open_w(outp), indent=2)
    rub = cell.get("rubric")
    rub_s = f" rubric={rub['avg']}" if rub else ""
    print(f"[cell] {cond:<11} {domain:<10} t{tid:<3} kpi={cell['kpi_rate']:.2f} "
          f"({sum(ach)}/{len(gold)}){rub_s}", flush=True)


def _open_w(p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return open(p, "w", encoding="utf-8")


# ---------- orchestration ------------------------------------------------
def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "all"

    if phase in ("gold", "all"):
        print(f"=== PHASE A: gold milestones ({len(DOMAINS)*len(TASK_IDS)} tasks) ===", flush=True)
        jobs = [(d, t) for d in DOMAINS for t in TASK_IDS]
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = [ex.submit(gen_gold, d, t) for d, t in jobs]
            for _ in as_completed(futs):
                pass

    if phase in ("score", "all"):
        print(f"=== PHASE B+C: scoring ({len(CONDS)*len(DOMAINS)*len(TASK_IDS)} cells) ===", flush=True)
        jobs = [(c, d, t) for c in CONDS for d in DOMAINS for t in TASK_IDS]
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = [ex.submit(score_cell, c, d, t) for c, d, t in jobs]
            for _ in as_completed(futs):
                pass

    aggregate()


def aggregate():
    agg = {}
    for cond in CONDS:
        agg[cond] = {}
        for domain in DOMAINS:
            rates, rubrics = [], []
            for tid in TASK_IDS:
                p = os.path.join(CELL_DIR, cond, domain, f"task_{tid}.json")
                if not os.path.exists(p):
                    continue
                c = json.load(open(p, encoding="utf-8"))
                rates.append(c.get("kpi_rate", 0.0))
                if c.get("rubric"):
                    rubrics.append(c["rubric"]["avg"])
            entry = {"n": len(rates),
                     "kpi_rate": round(sum(rates) / len(rates), 4) if rates else None}
            if rubrics:
                entry["rubric_avg"] = round(sum(rubrics) / len(rubrics), 3)
            agg[cond][domain] = entry
        # overall milestone-KPI across domains
        all_rates = [agg[cond][d]["kpi_rate"] for d in DOMAINS
                     if agg[cond][d]["kpi_rate"] is not None]
        agg[cond]["OVERALL_kpi"] = round(sum(all_rates) / len(all_rates), 4) if all_rates else None

    out = {
        "metric_primary": "MARBLE milestone-KPI achievement rate (shared gold milestones per task, achieved/total)",
        "metric_secondary": "coding domain rubric 1-5 (correctness/completeness/quality)",
        "judge": "claude-opus-4.6 via Copilot CLI (same-family judge; applied uniformly to all conditions; disclosed)",
        "conditions": CONDS,
        "domains": DOMAINS,
        "n_per_cell": len(TASK_IDS),
        "subset_task_ids": TASK_IDS,
        "results": agg,
    }
    json.dump(out, open(os.path.join(QA, "quality_ablation_results.json"), "w", encoding="utf-8"), indent=2)
    print("\n===== AGGREGATE (milestone-KPI %) =====", flush=True)
    hdr = "cond".ljust(12) + "".join(d[:9].ljust(11) for d in DOMAINS) + "OVERALL"
    print(hdr, flush=True)
    for cond in CONDS:
        row = cond.ljust(12)
        for d in DOMAINS:
            v = agg[cond][d]["kpi_rate"]
            row += (f"{v*100:.1f}%").ljust(11) if v is not None else "n/a".ljust(11)
        ov = agg[cond]["OVERALL_kpi"]
        row += f"{ov*100:.1f}%" if ov is not None else "n/a"
        print(row, flush=True)


if __name__ == "__main__":
    main()
