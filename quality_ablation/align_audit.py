"""
Alignment auditor: for each domain and ablation task slot, map every condition's
output back to its TRUE MARBLE jsonl task by content overlap, then report whether
all conditions (with real output) solved the SAME jsonl task. This determines
which (domain, slot) cells support a clean same-prompt quality comparison.
"""
import json, os, re
from collections import defaultdict

WT = (r"C:\Users\tamirdresher\.copilot\repos\copilot-worktrees\tamresearch1"
      r"\tamirdresher-microsoft-fluffy-dollop\squad-marble")
MBROOT = os.path.join(WT, "marble-upstream", "multiagentbench")
RES = os.path.join(WT, "results")
COND_DIR = {"full_squad": "result_squad-copilot-cli", "coord_only": "result_coord-only",
            "no_squad": "result_no-squad-expanded", "memory_only": "result_memory-only"}
DB_RERUN = os.path.join(RES, "rerun_no-squad-database")
DOMAINS = ["coding", "research", "bargaining", "database"]
SLOTS = ["1","10","20","30","40","50","60","70","80","90"]
STOP = set("please write program called system that facilitates the collaborative "
           "software development task application business dear research team you are "
           "collaborating generate based following introduction analysis negotiation "
           "product this with from have will your they their which agents agent".split())

def toks(s):
    return {w for w in re.findall(r"[a-z0-9]{6,}", (s or "").lower()) if w not in STOP}

def load_jsonl(dom):
    p = os.path.join(MBROOT, dom, f"{dom}_main.jsonl")
    out = {}
    for line in open(p, encoding="utf-8"):
        if line.strip():
            r = json.loads(line); out[str(r["task_id"])] = r["task"]["content"]
    return out

def load_out(cond, dom, slot):
    if cond == "no_squad" and dom == "database":
        p = os.path.join(DB_RERUN, f"task_{slot}.json")
    else:
        p = os.path.join(RES, COND_DIR[cond], dom, f"task_{slot}.json")
    if not os.path.exists(p): return None
    d = json.load(open(p, encoding="utf-8-sig"))
    o = d.get("output") or d.get("final_output") or ""
    if not isinstance(o, str) or not o.strip(): return None
    if o.strip().upper().startswith(("NO-FILE-OUTPUT","TIMEOUT")): return None
    return o

def best_match(otoks, jtok):
    best, bid = -1, None
    for tid, jt in jtok.items():
        inter = len(otoks & jt)
        if inter > best: best, bid = inter, tid
    return bid, best

for dom in DOMAINS:
    jj = load_jsonl(dom); jtok = {t: toks(c) for t, c in jj.items()}
    print(f"\n===== {dom} =====")
    for slot in SLOTS:
        mapped = {}
        for cond in COND_DIR:
            o = load_out(cond, dom, slot)
            if o is None: mapped[cond] = None
            else:
                bid, sc = best_match(toks(o), jtok)
                mapped[cond] = bid if sc >= 3 else "?"
        real = [v for v in mapped.values() if v not in (None, "?")]
        aligned = len(set(real)) == 1 and len(real) >= 2
        ids = set(real)
        tag = "OK" if aligned and len(real) == 4 else ("PARTIAL" if aligned else "MISALIGNED")
        print(f"  slot {slot:<3} -> "
              + " ".join(f"{c}={mapped[c]}" for c in COND_DIR)
              + f"   [{tag}] jsonl_ids={sorted(ids)}")
