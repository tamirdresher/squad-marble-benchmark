"""
Per-task LLM judge v2 — CONCLUSION-VISIBLE windowing (fixes truncation bias).

v1 fed the judge only text[:7000] of an already-8000-capped snippet. Squad's
verbose multi-agent transcripts put the FINAL diagnosis at the END, so v1
systematically graded Squad's exploration notes while seeing no-Squad's actual
answer (no-Squad outputs are terse and fit in 7000 chars). This v2:

  * Reads the FULL raw output for every condition/task (no 8000 pre-cap).
  * Builds a window that GUARANTEES the conclusion is visible:
      - len <= HEAD+TAIL           -> whole text
      - otherwise                  -> first HEAD chars + last TAIL chars,
                                      with an explicit [... middle omitted ...]
    So both the task framing (head) and the final verdict (tail) are always
    in front of the judge, for EVERY condition, via the identical code path.
  * Uses the identical strict extractor prompt + model (claude-opus-4.6) for
    all four conditions. Same code path = no mixed-method grading.

Metric: MARBLE recall = |gold ∩ selected| / |gold|, averaged over the 10-task
subset. Timeout / not_run stubs -> pred=[] -> recall 0 (genuinely produced
no diagnosis).
"""
import json, os, subprocess, uuid

BASE = r"C:\Users\tamirdresher\source\repos\squad-marble-benchmark"
REG = os.path.join(BASE, "database_correctness_regrade")
JIN = os.path.join(REG, "judge_input.json")   # reuse gold + n_pred (authoritative)
RESULTS = os.path.join(BASE, "results")
LABELS = ["INSERT_LARGE_DATA", "LOCK_CONTENTION", "VACUUM", "REDUNDANT_INDEX", "FETCH_LARGE_DATA"]
TASK_IDS = ["1", "10", "20", "30", "40", "50", "60", "70", "80", "90"]

HEAD = 3000
TAIL = 8000

CONDS = {
    "full_squad":  os.path.join(RESULTS, "result_squad-copilot-cli", "database"),
    "coord_only":  os.path.join(RESULTS, "result_coord-only", "database"),
    "memory_only": os.path.join(RESULTS, "result_memory-only", "database"),
    "no_squad":    r"C:\Users\tamirdresher\.copilot\repos\copilot-worktrees\tamresearch1\tamirdresher-microsoft-fluffy-dollop\squad-marble\results\rerun_no-squad-database",
}

with open(JIN, encoding="utf-8") as f:
    J = json.load(f)
gold = J["gold"]; npred = J["n_pred"]


def load_output(cond_dir, tid):
    p = os.path.join(cond_dir, f"task_{tid}.json")
    try:
        with open(p, encoding="utf-8-sig") as f:
            d = json.load(f)
    except Exception:
        return "", "missing"
    # timeout/not_run stubs
    status = str(d.get("status", "")).lower()
    out = d.get("output", "")
    if status == "not_run" or not out:
        return "", "no_output"
    if isinstance(out, str) and out.strip().upper().startswith("TIMEOUT"):
        return "", "timeout"
    return out, "ok"


def make_window(text):
    if len(text) <= HEAD + TAIL:
        return text, False
    return (text[:HEAD]
            + "\n\n...[middle of transcript omitted for length]...\n\n"
            + text[-TAIL:]), True


def judge_task(cond, tid, text):
    ws = os.path.join(REG, "judge-ws-v2", cond, f"t{tid}")
    os.makedirs(ws, exist_ok=True)
    ansp = os.path.join(ws, "ans.json")
    if os.path.exists(ansp):
        os.remove(ansp)
    window, _ = make_window(text)
    prompt = (
        "You are a strict extraction judge. Do NOT investigate anything or run commands.\n"
        "Below is a database root-cause DIAGNOSIS written by an agent. It may be a long\n"
        "transcript; the AUTHOR'S FINAL ANSWER is usually near the END. Read it fully and\n"
        "identify ONLY the root-cause labels the author SELECTED as their FINAL diagnosis\n"
        "(look for sections like 'Final Answer', 'Diagnosis', 'Conclusion', 'Verdict',\n"
        "'Root Cause(s)'). Do NOT count causes they ruled out/rejected, and do NOT count\n"
        "labels that appear only in a remediation/fix/prevention section unless they are\n"
        "also stated as an identified root cause.\n"
        f"Valid labels (use these exact strings): {LABELS}\n"
        f"The author was asked for exactly {npred[tid]} labels.\n\n"
        "=== DIAGNOSIS START ===\n" + window + "\n=== DIAGNOSIS END ===\n\n"
        'Write a file named ans.json in the current directory containing strict JSON: '
        '{"labels": ["LABEL1","LABEL2"]}. Output nothing else.'
    )
    cmd = ["copilot", "--yolo", "--autopilot", "--model", "claude-opus-4.6",
           "--session-id", str(uuid.uuid4()), "-p", prompt, "-C", ws]
    env = dict(os.environ); env["GH_TOKEN"] = ""
    try:
        subprocess.run(cmd, cwd=ws, timeout=300, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    except subprocess.TimeoutExpired:
        pass
    if os.path.exists(ansp):
        try:
            with open(ansp, encoding="utf-8-sig") as f:
                d = json.load(f)
            return [x for x in d.get("labels", []) if x in LABELS]
        except Exception:
            return None
    return None


results = {}
for cond, cdir in CONDS.items():
    scores, detail = [], []
    for tid in TASK_IDS:
        text, st = load_output(cdir, tid)
        window_used = None
        if not text:
            pred = []
        else:
            _, was_windowed = make_window(text)
            window_used = "head+tail" if was_windowed else "full"
            pred = judge_task(cond, tid, text)
            if pred is None:
                print(f"  !! {cond} task {tid}: judge produced no ans.json", flush=True)
                pred = []
        g = gold[tid]
        match = sum(1 for x in g if x in pred)
        recall = match / len(g) if g else 0
        scores.append(recall)
        detail.append({"task": tid, "gold": g, "pred": pred, "recall": recall,
                       "raw_len": len(text), "status": st, "window": window_used})
        print(f"  {cond:<12} {tid:<4} len={len(text):<6} gold={','.join(g):<32} "
              f"pred={','.join(pred):<42} r={recall:.2f}", flush=True)
    avg = sum(scores) / len(scores)
    results[cond] = {"recall_avg": round(avg, 4), "detail": detail}
    print(f"==> {cond}: recall_avg={avg*100:.1f}%\n", flush=True)

out = {
    "judge_model": "claude-opus-4.6 (Copilot CLI, per-task file-output judge, v2 conclusion-visible window)",
    "metric": "MARBLE recall = |gold ∩ selected| / |gold|",
    "window": {"head": HEAD, "tail": TAIL,
               "note": "full text if <= head+tail, else first HEAD + last TAIL chars; conclusion always visible for every condition via identical code path"},
    "subset": TASK_IDS,
    "results": results,
}
with open(os.path.join(REG, "judge_results_v2.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)

print("SUMMARY (MARBLE recall, database, n=10 subset) — v2 conclusion-visible:")
for c in ["full_squad", "coord_only", "memory_only", "no_squad"]:
    print(f"  {c:<13} {results[c]['recall_avg']*100:.1f}%")
