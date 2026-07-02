"""
UNIFORM correctness/quality grading of the FRESH ALIGNED coding+database rerun
(produced by rerun_aligned_coding_db.py). Every condition solved the SAME jsonl
task at each task_id (alignment guaranteed by construction), so this is a clean
same-task comparison — the thing that forced coding/database out of the earlier
2-domain table is now fixed.

One judge call per cell returns BOTH the milestone-KPI achievement vector and a
1-5 output-quality rubric, graded uniformly with the SAME model/prompt/gold
across every condition (matches regrade_aligned.py exactly).

Source:  results/aligned_rerun/{cond}/{domain}/task_{id}.json
Output:  aligned_cells/{cond}/{domain}/task_{id}.json
Judge:   claude-opus-4.6 (same-family caveat noted; gpt-4o cross-check in aggregate).

Launches are staggered + token pre-warmed to avoid the MSAL token-cache lock
stampede that deadlocks parallel copilot cold-starts.
"""
import json, os, subprocess, uuid, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

QA = os.path.dirname(os.path.abspath(__file__))
WS = os.path.join(QA, "judge-ws", "aligned_rerun")
WT = (r"C:\Users\tamirdresher\.copilot\repos\copilot-worktrees\tamresearch1"
      r"\tamirdresher-microsoft-fluffy-dollop\squad-marble")
MBROOT = os.path.join(WT, "marble-upstream", "multiagentbench")
RERUN = os.path.join(WT, "results", "aligned_rerun")

CONDS = ["no_squad", "memory_only", "coord_only", "full_squad"]
DOMAINS = ["coding", "database"]
IDS = ["1", "10", "20", "30", "40", "50", "60", "70", "80", "90"]
WORKERS = 4
STAGGER = 20

_launch_lock = threading.Lock()

def prewarm_token():
    try:
        subprocess.run(["az", "account", "get-access-token", "--resource",
                        "499b84ac-1321-427f-aa17-267ca6975798", "--output", "none"],
                       timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

_tc = {}
def task_content(dom, tid):
    if dom not in _tc:
        p = os.path.join(MBROOT, dom, f"{dom}_main.jsonl")
        _tc[dom] = {str(json.loads(l)["task_id"]): json.loads(l)["task"]["content"]
                    for l in open(p, encoding="utf-8") if l.strip()}
    return _tc[dom][tid]

def load_out(cond, dom, tid):
    p = os.path.join(RERUN, cond, dom, f"task_{tid}.json")
    if not os.path.exists(p): return "", "missing"
    d = json.load(open(p, encoding="utf-8-sig"))
    o = d.get("output") or ""
    if not o: return "", "no_output"
    if isinstance(o, str) and o.strip().upper().startswith(("NO-FILE-OUTPUT", "TIMEOUT")):
        return "", "no_output"
    return o, "ok"

def gold(dom, tid):
    return json.load(open(os.path.join(QA, "gold", dom, f"task_{tid}.json"),
                          encoding="utf-8"))["milestones"]

def judge_cell(dom, cond, slot):
    outp = os.path.join(QA, "aligned_cells", cond, dom); os.makedirs(outp, exist_ok=True)
    outf = os.path.join(outp, f"task_{slot}.json")
    if os.path.exists(outf):
        print(f"[skip] {dom} {cond} t{slot}", flush=True); return
    text, status = load_out(cond, dom, slot); g = gold(dom, slot)
    cell = {"domain": dom, "cond": cond, "task": slot, "status": status, "raw_len": len(text),
            "n_gold": len(g), "grading": "aligned-rerun-v1"}
    if not text:
        cell["kpi_achieved"] = [False]*len(g); cell["kpi_rate"] = 0.0
        cell["rubric"] = {"correctness": 1, "completeness": 1, "quality": 1, "avg": 1.0}
        json.dump(cell, open(outf, "w", encoding="utf-8"), indent=2)
        print(f"[aligned] {dom} {cond:<11} t{slot:<3} EMPTY ({status})", flush=True); return
    ws = os.path.join(WS, dom, cond, f"t{slot}"); os.makedirs(ws, exist_ok=True)
    gl = "\n".join(f"{i+1}. {m}" for i, m in enumerate(g))
    body = (f"# TASK ({dom})\n{task_content(dom,slot)[:2500]}\n\n"
            f"# GOLD MILESTONES ({len(g)})\n{gl}\n\n# AGENT OUTPUT\n{text[:24000]}\n")
    open(os.path.join(ws, "input.md"), "w", encoding="utf-8").write(body)
    ansp = os.path.join(ws, "ans.json")
    if os.path.exists(ansp): os.remove(ansp)
    prompt = ("Read input.md in the current directory (do NOT run code). It has a TASK, "
              "GOLD MILESTONES, and an AGENT OUTPUT. Judge ONLY from the agent output.\n"
              "1) For EACH gold milestone decide achieved true/false (strict).\n"
              "2) Rate the output 1-5 on correctness, completeness, quality.\n"
              f'Write ans.json: {{"achieved":[{len(g)} booleans],'
              '"correctness":N,"completeness":N,"quality":N}. Nothing else.')
    cmd = ["copilot", "--yolo", "--autopilot", "--model", "claude-opus-4.6",
           "--session-id", str(uuid.uuid4()), "-p", prompt, "-C", ws]
    env = dict(os.environ); env["GH_TOKEN"] = ""
    try:
        with _launch_lock:
            proc = subprocess.Popen(cmd, cwd=ws, env=env, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            time.sleep(STAGGER)
    except Exception as e:
        print(f"[ERR ] {dom} {cond} t{slot} spawn: {e}", flush=True); return
    t0 = time.time()
    while time.time() - t0 < 360:
        time.sleep(10)
        if os.path.exists(ansp) and os.path.getsize(ansp) > 10:
            time.sleep(3); break
        if proc.poll() is not None:
            break
    if proc.poll() is None:
        try: subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                            timeout=20, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception: pass
    ach = []; rub = None
    if os.path.exists(ansp):
        try:
            d = json.load(open(ansp, encoding="utf-8-sig"))
            ach = [bool(x) for x in d.get("achieved", [])][:len(g)]
            c, cm, q = [max(1, min(5, int(d.get(k, 3)))) for k in ("correctness", "completeness", "quality")]
            rub = {"correctness": c, "completeness": cm, "quality": q, "avg": round((c+cm+q)/3, 2)}
        except Exception: pass
    while len(ach) < len(g): ach.append(False)
    cell["kpi_achieved"] = ach; cell["kpi_rate"] = round(sum(ach)/len(g), 4) if g else 0.0
    cell["rubric"] = rub
    json.dump(cell, open(outf, "w", encoding="utf-8"), indent=2)
    print(f"[aligned] {dom} {cond:<11} t{slot:<3} kpi={cell['kpi_rate']:.2f} "
          f"rub={rub['avg'] if rub else None} len={len(text)}", flush=True)

if __name__ == "__main__":
    jobs = [(dom, cond, slot) for dom in DOMAINS for cond in CONDS for slot in IDS]
    print(f"total cells: {len(jobs)} (workers={WORKERS})", flush=True)
    print("prewarming az token cache ...", flush=True); prewarm_token()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(judge_cell, *j) for j in jobs]
        for _ in as_completed(futs): pass
    print("aligned coding+database regrade done", flush=True)
