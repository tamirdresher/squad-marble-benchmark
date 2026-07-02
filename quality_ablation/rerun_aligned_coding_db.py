"""
FRESH ALIGNED RERUN of all 4 conditions on coding + database, on the SAME
task ids per domain, so task_id N == the same MARBLE task in every condition
(alignment guaranteed by construction — fixes the divergence that forced
coding/database out of the correctness table).

Factorial (coordination x memory):
  full_squad  = +coord +mem : copy squad template ws (has .squad/decisions.md), --agent squad
  coord_only  = +coord -mem : copy squad template ws, blank decisions.md, --agent squad
  memory_only = -coord +mem : raw ws, decisions.md injected into prompt (first 8000 chars)
  no_squad    = -coord -mem : raw ws, plain prompt

Output -> results/aligned_rerun/{cond}/{domain}/task_{id}.json  (schema matches
the original ablation-runner: {metadata, task_id, domain, model, output}).
Same model (claude-opus-4.6) everywhere. Resumable (skips completed cells).
"""
import json, os, re, shutil, subprocess, time, uuid, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Serialize copilot cold-starts: 4 instances hitting `az account get-access-token`
# at the same instant deadlock on the MSAL token-cache file lock. Staggering the
# Popen launches (token cache is shared+warm after the first) removes the stampede.
_launch_lock = threading.Lock()
STAGGER = 25  # seconds between successive copilot launches

def prewarm_token():
    try:
        subprocess.run(["az", "account", "get-access-token", "--resource",
                        "499b84ac-1321-427f-aa17-267ca6975798", "--output", "none"],
                       timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

WT = (r"C:\Users\tamirdresher\.copilot\repos\copilot-worktrees\tamresearch1"
      r"\tamirdresher-microsoft-fluffy-dollop\squad-marble")
MBROOT = os.path.join(WT, "marble-upstream", "multiagentbench")
OUTROOT = os.path.join(WT, "results", "aligned_rerun")
WSROOT = os.path.join(WT, "rerun-ws-aligned")
TEMPLATE = os.path.join(WT, "workspaces")  # workspaces/{domain} = squad template

CONDS = ["no_squad", "memory_only", "coord_only", "full_squad"]
DOMAINS = ["coding", "database"]
IDS = [1, 10, 20, 30, 40, 50, 60, 70, 80, 90]
OUTFILE = {"coding": "solution.py", "database": "answer.md"}
MODEL = "claude-opus-4.6"
TIMEOUT = 700
POLL = 20
WORKERS = 4

_tasks = {}
def tasks(dom):
    if dom not in _tasks:
        p = os.path.join(MBROOT, dom, f"{dom}_main.jsonl")
        _tasks[dom] = {int(json.loads(l)["task_id"]): json.loads(l)
                       for l in open(p, encoding="utf-8") if l.strip()}
    return _tasks[dom]

_dec = {}
def decisions(dom):
    if dom not in _dec:
        p = os.path.join(TEMPLATE, dom, ".squad", "decisions.md")
        try:
            _dec[dom] = open(p, encoding="utf-8", errors="replace").read()
        except FileNotFoundError:
            _dec[dom] = ""
    return _dec[dom]

def build_prompt(dom, task, inject_memory):
    tid = task["task_id"]; content = task["task"]["content"]
    ofmt = task["task"].get("output_format", "")
    if dom == "coding":
        p = (f"MARBLE Benchmark Task #{tid} (coding)\n\n"
             "Complete this software development task. Produce the final code as solution.py.\n"
             "Write the complete implementation with all classes, functions, and logic.\n\n"
             f"--- TASK ---\n{content}\n--- END TASK ---\n\n"
             f"Output format: {ofmt}\n\n"
             "Produce the complete solution.py. Write all code to solution.py in the current directory.")
    else:
        p = (f"MARBLE Benchmark Task #{tid} (database diagnosis)\n\n"
             "You are diagnosing a database performance anomaly.\n\n"
             f"--- TASK ---\n{content}\n--- END TASK ---\n\n"
             f"{ofmt}\n\n"
             "Write your final diagnosis to answer.md.")
    if inject_memory:
        d = decisions(dom)[:8000]
        if d:
            p = f"CONTEXT FROM PRIOR TASKS (use this knowledge):\n{d}\n\n---\n\n{p}"
    return p

_ignore = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache",
                                 ".benchmarks", "results", "*.pyc")

def make_ws(cond, dom, tid):
    ws = os.path.join(WSROOT, cond, dom, f"t{tid}")
    if os.path.exists(ws):
        shutil.rmtree(ws, ignore_errors=True)
    if cond in ("full_squad", "coord_only"):
        shutil.copytree(os.path.join(TEMPLATE, dom), ws, ignore=_ignore)
        # clean any leftover artifacts from the template
        for f in ("solution.py", "answer.md", "task_prompt.md", "test_solution.py"):
            try: os.remove(os.path.join(ws, f))
            except OSError: pass
        if cond == "coord_only":
            dp = os.path.join(ws, ".squad", "decisions.md")
            if os.path.exists(dp):
                open(dp, "w", encoding="utf-8").write(
                    "# Decisions\n\n_(no carried memory — coord-only ablation)_\n")
    else:
        os.makedirs(ws, exist_ok=True)
    return ws

def already_done(cond, dom, tid):
    p = os.path.join(OUTROOT, cond, dom, f"task_{tid}.json")
    if not os.path.exists(p): return False
    try:
        d = json.load(open(p, encoding="utf-8-sig"))
        o = d.get("output", "")
        return isinstance(o, str) and len(o) >= 100 and not o.upper().startswith("TIMEOUT")
    except Exception:
        return False

def run_cell(cond, dom, tid):
    if already_done(cond, dom, tid):
        print(f"[skip] {cond} {dom} t{tid}", flush=True); return
    task = tasks(dom)[tid]
    inject = cond == "memory_only"
    prompt = build_prompt(dom, task, inject)
    ws = make_ws(cond, dom, tid)
    outname = OUTFILE[dom]
    outpath = os.path.join(ws, outname)
    cmd = ["copilot", "--yolo", "--autopilot", "--model", MODEL,
           "--session-id", str(uuid.uuid4()), "-p", prompt, "-C", ws]
    if cond in ("full_squad", "coord_only"):
        cmd += ["--agent", "squad"]
    env = dict(os.environ)
    env["GH_TOKEN"] = ""; env["cli_resume"] = ""; env["MSFT_AGENCY"] = ""
    env["AGENCY_SESSION_ID"] = ""
    t0 = time.time()
    print(f"[run ] {cond} {dom} t{tid} ...", flush=True)
    try:
        with _launch_lock:
            proc = subprocess.Popen(cmd, cwd=ws, env=env, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            time.sleep(STAGGER)  # let this instance settle its az token before the next launches
    except Exception as e:
        print(f"[ERR ] {cond} {dom} t{tid} spawn failed: {e}", flush=True); return
    found = False
    while time.time() - t0 < TIMEOUT:
        time.sleep(POLL)
        if os.path.exists(outpath) and os.path.getsize(outpath) > 100:
            time.sleep(20); found = True; break
        if proc.poll() is not None:
            # process ended; give the file a moment then stop
            if os.path.exists(outpath) and os.path.getsize(outpath) > 100:
                found = True
            break
    if proc.poll() is None:
        try: subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                            timeout=20, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception: pass
        try: proc.wait(timeout=15)
        except Exception:
            try: proc.kill()
            except Exception: pass
    elapsed = round(time.time() - t0, 1)
    answer = ""
    if os.path.exists(outpath):
        answer = open(outpath, encoding="utf-8", errors="replace").read()
    produced = bool(answer) and len(answer) >= 50
    if not produced:
        answer = f"TIMEOUT: Task did not produce {outname} within {TIMEOUT}s"
    res = {"metadata": {"condition": cond, "domain": dom,
                        "execution_time_seconds": elapsed, "produced_output": produced,
                        "aligned_rerun": True, "factorial": True},
           "task_id": tid, "domain": dom, "model": "claude-opus-4-6", "output": answer}
    od = os.path.join(OUTROOT, cond, dom); os.makedirs(od, exist_ok=True)
    json.dump(res, open(os.path.join(od, f"task_{tid}.json"), "w", encoding="utf-8"),
              indent=2)
    # free disk from the heavy squad ws copy
    if cond in ("full_squad", "coord_only"):
        shutil.rmtree(ws, ignore_errors=True)
    print(f"[done] {cond} {dom} t{tid} produced={produced} "
          f"{round(len(answer)/1024,1)}KB {elapsed}s", flush=True)

if __name__ == "__main__":
    import sys
    only = sys.argv[1] if len(sys.argv) > 1 else None  # optional: cond filter
    jobs = [(c, d, i) for c in CONDS for d in DOMAINS for i in IDS
            if (only is None or c == only)]
    print(f"total cells: {len(jobs)} (workers={WORKERS}, timeout={TIMEOUT}s)", flush=True)
    print("prewarming az token cache ...", flush=True); prewarm_token()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(run_cell, *j) for j in jobs]
        for _ in as_completed(futs): pass
    print("aligned rerun done", flush=True)
