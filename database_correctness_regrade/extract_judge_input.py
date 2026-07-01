"""
Step 1: Extract a generous 'decision region' snippet from each condition/task output
so an LLM judge can identify the predicted root causes. No label parsing here —
just isolate the human-readable diagnosis text.
"""
import json, os, re

DB = r"C:\Users\tamirdresher\.copilot\repos\copilot-worktrees\tamresearch1\tamirdresher-microsoft-fluffy-dollop\squad-marble\marble-upstream\multiagentbench\database\database_main.jsonl"
PUB = r"C:\Users\tamirdresher\source\repos\squad-marble-benchmark\results"
RR = r"C:\Users\tamirdresher\.copilot\repos\copilot-worktrees\tamresearch1\tamirdresher-microsoft-fluffy-dollop\squad-marble\results\rerun_no-squad-database"
OUT = r"C:\Users\tamirdresher\.copilot\repos\copilot-worktrees\tamresearch1\tamirdresher-microsoft-fluffy-dollop\squad-marble\judge_input.json"

gold, npred = {}, {}
with open(DB, encoding="utf-8") as f:
    for line in f:
        t = json.loads(line)
        gold[t["task_id"]] = t["task"]["root_causes"]
        npred[t["task_id"]] = t["task"].get("number_of_labels_pred", 2)

TASK_IDS = [1,10,20,30,40,50,60,70,80,90]
CONDS = {
    "full_squad":  os.path.join(PUB, "result_squad-copilot-cli", "database"),
    "coord_only":  os.path.join(PUB, "result_coord-only", "database"),
    "memory_only": os.path.join(PUB, "result_memory-only", "database"),
    "no_squad":    RR,
}

def load(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f).get("output", "")
    except Exception:
        return ""

data = {"gold": {str(k): gold[k] for k in TASK_IDS},
        "n_pred": {str(k): npred[k] for k in TASK_IDS},
        "conditions": {}}
for cond, d in CONDS.items():
    data["conditions"][cond] = {}
    for tid in TASK_IDS:
        out = load(os.path.join(d, f"task_{tid}.json"))
        # keep full output (cap 8000) so the judge sees the conclusion too
        snippet = out[:8000] if out else ""
        data["conditions"][cond][str(tid)] = snippet

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
print(f"Wrote judge input for {len(TASK_IDS)} tasks x {len(CONDS)} conditions to {OUT}")
# quick report of which are empty
for cond in CONDS:
    empty = [t for t in TASK_IDS if not data["conditions"][cond][str(t)]]
    print(f"  {cond}: {10-len(empty)}/10 have output; empty tasks: {empty}")
