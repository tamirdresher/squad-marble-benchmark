"""
Re-grade CODING with FULL code visible (fixes the windowing artifact).

The main run windowed every output to head3k+tail8k. Coding deliverables are
35-90 KB single-file programs; windowing hid the middle (most feature impls),
so milestone/rubric scores tracked whether the *visible* head docstring happened
to enumerate features rather than actual completeness. Here we feed the ENTIRE
code to the judge via a file (input.md) to avoid the ~32 KB Windows command-line
limit, using ONE identical judge call per (condition, task).

Overwrites quality_ablation/cells/{cond}/coding/task_{id}.json with a
`grading: "full-code-v2"` marker.
"""
import json, os, subprocess, uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

QA = os.path.dirname(os.path.abspath(__file__))
WS = os.path.join(QA, "judge-ws", "coding_full")
WT = (r"C:\Users\tamirdresher\.copilot\repos\copilot-worktrees\tamresearch1"
      r"\tamirdresher-microsoft-fluffy-dollop\squad-marble")
MB = os.path.join(WT, "marble-upstream", "multiagentbench", "coding", "coding_main.jsonl")
RES = os.path.join(WT, "results")
COND_DIR = {"full_squad": "result_squad-copilot-cli", "coord_only": "result_coord-only",
            "no_squad": "result_no-squad-expanded", "memory_only": "result_memory-only"}
CONDS = list(COND_DIR)
TASK_IDS = ["1", "10", "20", "30", "40", "50", "60", "70", "80", "90"]
WORKERS = 4

_tasks = None
def task_content(tid):
    global _tasks
    if _tasks is None:
        _tasks = {}
        for line in open(MB, encoding="utf-8"):
            if line.strip():
                r = json.loads(line); _tasks[str(r["task_id"])] = r["task"]["content"]
    return _tasks[tid]

def load_output(cond, tid):
    p = os.path.join(RES, COND_DIR[cond], "coding", f"task_{tid}.json")
    if not os.path.exists(p): return "", "missing"
    d = json.load(open(p, encoding="utf-8-sig"))
    out = d.get("output") or d.get("final_output") or ""
    if not out: return "", "no_output"
    if isinstance(out, str) and out.strip().upper().startswith("TIMEOUT"): return "", "timeout"
    return out, "ok"

def load_gold(tid):
    return json.load(open(os.path.join(QA, "gold", "coding", f"task_{tid}.json"), encoding="utf-8"))["milestones"]

def regrade(cond, tid):
    outp = os.path.join(QA, "cells", cond, "coding", f"task_{tid}.json")
    text, status = load_output(cond, tid)
    gold = load_gold(tid)
    cell = {"cond": cond, "domain": "coding", "task": tid, "status": status,
            "raw_len": len(text), "n_gold": len(gold), "grading": "full-code-v2"}
    if not text:
        cell["kpi_achieved"] = [False]*len(gold); cell["kpi_rate"] = 0.0
        cell["rubric"] = {"correctness":1,"completeness":1,"quality":1,"avg":1.0}
        json.dump(cell, open(outp,"w",encoding="utf-8"), indent=2)
        print(f"[coding-v2] {cond:<11} t{tid:<3} EMPTY({status})", flush=True); return
    ws = os.path.join(WS, cond, f"t{tid}"); os.makedirs(ws, exist_ok=True)
    gold_lines = "\n".join(f"{i+1}. {m}" for i,m in enumerate(gold))
    content = task_content(tid)
    input_md = (f"# TASK (coding)\n{content[:3000]}\n\n"
                f"# GOLD MILESTONES ({len(gold)})\n{gold_lines}\n\n"
                f"# AGENT CODE OUTPUT (full)\n{text}\n")
    open(os.path.join(ws,"input.md"),"w",encoding="utf-8").write(input_md)
    ansp = os.path.join(ws,"ans.json")
    if os.path.exists(ansp): os.remove(ansp)
    prompt = (
        "Read the file input.md in the current directory (do NOT run any code). It "
        "contains a TASK, a list of GOLD MILESTONES, and the FULL source code an agent "
        "produced. Judge ONLY from the code present in input.md.\n"
        "1) For EACH gold milestone decide achieved true/false (strict: the code must "
        "actually implement it, not merely mention it).\n"
        "2) Rate the code 1-5 on correctness, completeness, quality.\n"
        f'Write ans.json: {{"achieved":[{len(gold)} booleans in order],'
        '"correctness":N,"completeness":N,"quality":N}. Output nothing else.')
    cmd = ["copilot","--yolo","--autopilot","--model","claude-opus-4.6",
           "--session-id",str(uuid.uuid4()),"-p",prompt,"-C",ws]
    env = dict(os.environ); env["GH_TOKEN"]=""
    try:
        subprocess.run(cmd, cwd=ws, timeout=420, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    except subprocess.TimeoutExpired:
        pass
    ach=[]; rub=None
    if os.path.exists(ansp):
        try:
            d=json.load(open(ansp,encoding="utf-8-sig"))
            ach=[bool(x) for x in d.get("achieved",[])][:len(gold)]
            c,cm,q=[max(1,min(5,int(d.get(k,3)))) for k in ("correctness","completeness","quality")]
            rub={"correctness":c,"completeness":cm,"quality":q,"avg":round((c+cm+q)/3,2)}
        except Exception: pass
    while len(ach)<len(gold): ach.append(False)
    cell["kpi_achieved"]=ach; cell["kpi_rate"]=round(sum(ach)/len(gold),4) if gold else 0.0
    cell["rubric"]=rub
    json.dump(cell, open(outp,"w",encoding="utf-8"), indent=2)
    print(f"[coding-v2] {cond:<11} t{tid:<3} len={len(text):<6} kpi={cell['kpi_rate']:.2f} "
          f"({sum(ach)}/{len(gold)}) rubric={rub['avg'] if rub else None}", flush=True)

if __name__ == "__main__":
    jobs=[(c,t) for c in CONDS for t in TASK_IDS]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs=[ex.submit(regrade,c,t) for c,t in jobs]
        for _ in as_completed(futs): pass
    print("coding full-code re-grade done", flush=True)
