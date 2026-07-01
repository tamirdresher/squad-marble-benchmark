"""
Reliable per-slot alignment verifier. For each ablation slot (1,10,20..90) and
each domain, take the RAREST distinctive tokens from the MARBLE jsonl task whose
id == slot, and check whether each condition's slot-N output contains at least
one of them. If all conditions-with-output do -> that slot is aligned (they all
solved the same prompt). Uses jsonl-native rare tokens = far more reliable than
cross-doc IDF argmax.
"""
import json, os, re
from collections import Counter

WT = (r"C:\Users\tamirdresher\.copilot\repos\copilot-worktrees\tamresearch1"
      r"\tamirdresher-microsoft-fluffy-dollop\squad-marble")
MBROOT = os.path.join(WT, "marble-upstream", "multiagentbench")
RES = os.path.join(WT, "results")
COND_DIR = {"full_squad": "result_squad-copilot-cli", "coord_only": "result_coord-only",
            "no_squad": "result_no-squad-expanded", "memory_only": "result_memory-only"}
DB_RERUN = os.path.join(RES, "rerun_no-squad-database")
SLOTS = ["1","10","20","30","40","50","60","70","80","90"]

def read_out(cond, dom, slot):
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

def load_jsonl(dom):
    p = os.path.join(MBROOT, dom, f"{dom}_main.jsonl")
    return {str(json.loads(l)["task_id"]): json.loads(l)["task"]["content"]
            for l in open(p, encoding="utf-8") if l.strip()}

for dom in ["coding","research","bargaining","database"]:
    jj = load_jsonl(dom)
    # global token frequency across all 100 jsonl contents
    gf = Counter()
    per = {}
    for tid, c in jj.items():
        ws = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_]{6,}", c))
        per[tid] = ws
        for w in ws: gf[w.lower()] += 1
    print(f"\n===== {dom} =====")
    aligned_ids = []
    for slot in SLOTS:
        if slot not in jj:
            print(f"  slot {slot}: no jsonl id"); continue
        # rarest tokens unique-ish to this task
        cand = sorted(per[slot], key=lambda w: gf[w.lower()])
        anchors = [w for w in cand if gf[w.lower()] <= 2][:6]
        if not anchors: anchors = cand[:6]
        anchors_l = [a.lower() for a in anchors]
        res = {}
        for cond in COND_DIR:
            o = read_out(cond, dom, slot)
            if o is None: res[cond] = "-"
            else:
                lo = o.lower()
                hit = sum(1 for a in anchors_l if a in lo)
                res[cond] = f"{hit}/{len(anchors_l)}"
        have = [c for c in COND_DIR if res[c] != "-"]
        ok = all(int(res[c].split("/")[0]) >= 1 for c in have) and len(have) >= 2
        four = len(have) == 4 and ok
        if four: aligned_ids.append(slot)
        tag = "ALIGNED4" if four else ("aligned" if ok else "MISALIGN")
        print(f"  slot {slot:<3} " + " ".join(f"{c}={res[c]}" for c in COND_DIR)
              + f"  anchors={anchors_l[:3]} [{tag}]")
    print(f"  >>> {dom} clean all-4 slots: n={len(aligned_ids)} -> {aligned_ids}")
