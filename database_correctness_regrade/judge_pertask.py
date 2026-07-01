"""
Per-task LLM judge (Copilot CLI). One call per task = small, reliable prompt.
Judge reads the FULL diagnosis and writes ans.json = {"labels": [...]} to its workspace.
Then compute MARBLE recall = |gold ∩ selected| / |gold|.
"""
import json, os, subprocess, uuid

BASE = r"C:\Users\tamirdresher\.copilot\repos\copilot-worktrees\tamresearch1\tamirdresher-microsoft-fluffy-dollop\squad-marble"
JIN = os.path.join(BASE, "judge_input.json")
LABELS = ["INSERT_LARGE_DATA","LOCK_CONTENTION","VACUUM","REDUNDANT_INDEX","FETCH_LARGE_DATA"]
TASK_IDS = ["1","10","20","30","40","50","60","70","80","90"]

with open(JIN, encoding="utf-8") as f:
    J = json.load(f)
gold = J["gold"]; npred = J["n_pred"]

def judge_task(cond, tid, text):
    ws = os.path.join(BASE, "judge-ws", cond, f"t{tid}")
    os.makedirs(ws, exist_ok=True)
    ansp = os.path.join(ws, "ans.json")
    if os.path.exists(ansp): os.remove(ansp)
    prompt = (
        "You are a strict extraction judge. Do NOT investigate anything or run commands.\n"
        "Below is a database root-cause DIAGNOSIS written by an agent. Read it fully and identify\n"
        "ONLY the root-cause labels the author SELECTED as their FINAL answer (look for sections like\n"
        "'Final Answer', 'Diagnosis', 'Conclusion', 'Verdict'). Ignore causes they ruled out/rejected.\n"
        f"Valid labels (use these exact strings): {LABELS}\n"
        f"The author was asked for exactly {npred[tid]} labels.\n\n"
        "=== DIAGNOSIS START ===\n" + text[:7000] + "\n=== DIAGNOSIS END ===\n\n"
        'Write a file named ans.json in the current directory containing strict JSON: '
        '{"labels": ["LABEL1","LABEL2"]}. Output nothing else.'
    )
    cmd = ["copilot","--yolo","--autopilot","--model","claude-opus-4.6",
           "--session-id",str(uuid.uuid4()),"-p",prompt,"-C",ws]
    env = dict(os.environ)
    try:
        subprocess.run(cmd, cwd=ws, timeout=300, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    except subprocess.TimeoutExpired:
        pass
    if os.path.exists(ansp):
        try:
            with open(ansp, encoding="utf-8-sig") as f:
                d = json.load(f)
            labs = d.get("labels", [])
            return [x for x in labs if x in LABELS]
        except Exception:
            return None
    return None

results = {}
for cond in ["full_squad","coord_only","no_squad"]:
    snips = J["conditions"][cond]
    scores, detail = [], []
    for tid in TASK_IDS:
        text = (snips[tid] or "").strip()
        if not text or text.upper().startswith("TIMEOUT"):
            pred = []
        else:
            pred = judge_task(cond, tid, text)
            if pred is None:
                print(f"  !! {cond} task {tid}: judge produced no ans.json"); pred = []
        g = gold[tid]
        match = sum(1 for x in g if x in pred)
        recall = match/len(g) if g else 0
        scores.append(recall)
        detail.append({"task":tid,"gold":g,"pred":pred,"recall":recall})
        print(f"  {cond:<11} {tid:<4} gold={','.join(g):<34} pred={','.join(pred):<40} r={recall:.2f}")
    avg = sum(scores)/len(scores)
    results[cond] = {"recall_avg":round(avg,4),"detail":detail}
    print(f"==> {cond}: recall_avg={avg*100:.1f}%\n")

results["memory_only"] = {"recall_avg":0.0,"detail":"all timeout_no_output"}
with open(os.path.join(BASE,"judge_results.json"),"w",encoding="utf-8") as f:
    json.dump({"judge_model":"claude-opus-4.6 (Copilot CLI, per-task file-output judge)",
               "metric":"MARBLE recall = |gold ∩ selected| / |gold|",
               "subset":TASK_IDS,"results":results}, f, indent=2)
print("SUMMARY (MARBLE recall, database, n=10 subset):")
for c in ["full_squad","coord_only","memory_only","no_squad"]:
    print(f"  {c:<13} {results[c]['recall_avg']*100:.1f}%")
