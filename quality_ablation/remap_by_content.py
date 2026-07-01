"""
Content re-map with STRONG per-domain anchors. Maps each condition's existing
output to the exact MARBLE jsonl task it solved (by program name / product code /
distinctive rare token), then reports the set of jsonl task_ids that ALL FOUR
conditions genuinely solved -- the only cells that support a clean same-prompt,
same-model quality/correctness comparison.
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
SLOTS = [str(i) for i in range(1, 101)]

def norm(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def read_out(cond, dom, slot):
    if cond == "no_squad" and dom == "database":
        p = os.path.join(DB_RERUN, f"task_{slot}.json")
    else:
        p = os.path.join(RES, COND_DIR[cond], dom, f"task_{slot}.json")
    if not os.path.exists(p): return None
    d = json.load(open(p, encoding="utf-8-sig"))
    o = d.get("output") or d.get("final_output") or ""
    if not isinstance(o, str) or not o.strip(): return None
    if o.strip().upper().startswith(("NO-FILE-OUTPUT", "TIMEOUT")): return None
    return o

def load_jsonl(dom):
    p = os.path.join(MBROOT, dom, f"{dom}_main.jsonl")
    return {str(json.loads(l)["task_id"]): json.loads(l)["task"]["content"]
            for l in open(p, encoding="utf-8") if l.strip()}

def anchors(dom, content):
    """Return list of strong normalized anchor strings for a jsonl task."""
    a = []
    if dom == "coding":
        for m in re.findall(r"called\s+([A-Za-z][A-Za-z0-9_ ]{2,40})", content):
            a.append(norm(m.split(" that ")[0].split(" is ")[0]))
    elif dom == "bargaining":
        a += [norm(x) for x in re.findall(r"\b([A-Z]{2,6}\d{2,5}[A-Z0-9]*)\b", content)]
    # generic: rarest long tokens as backup anchors
    toks = [t for t in re.findall(r"[A-Za-z]{7,}", content)]
    return [x for x in a if len(x) >= 5], toks

# Precompute per-domain jsonl anchors + global token doc-frequency
def match_id(dom, out, jj, janch, df, N):
    no = norm(out); low = out.lower()
    # 1) strong anchor: unique program name / product code present in output
    hits = [tid for tid, (strong, _) in janch.items() if strong and any(s in no for s in strong)]
    if len(set(hits)) == 1: return hits[0], "strong"
    # 2) rare-token score: sum of IDF for jsonl tokens appearing in output
    best, bid = 0.0, None
    for tid, c in jj.items():
        _, toks = janch[tid]
        sc = 0.0
        for t in set(toks):
            if t.lower() in low:
                sc += 1.0 / (1 + df.get(t.lower(), 0))
        if sc > best: best, bid = sc, tid
    return bid, f"idf={best:.2f}"

for dom in ["coding", "research", "bargaining", "database"]:
    jj = load_jsonl(dom)
    janch = {tid: anchors(dom, c) for tid, c in jj.items()}
    df = defaultdict(int)
    for tid, c in jj.items():
        for t in set(re.findall(r"[A-Za-z]{7,}", c.lower())): df[t] += 1
    N = len(jj)
    solved = {cond: {} for cond in COND_DIR}   # cond -> {jsonl_id: slot}
    conf = {cond: {} for cond in COND_DIR}
    for cond in COND_DIR:
        for slot in SLOTS:
            o = read_out(cond, dom, slot)
            if o is None: continue
            tid, how = match_id(dom, o, jj, janch, df, N)
            if tid is not None and tid not in solved[cond]:
                solved[cond][tid] = slot; conf[cond][tid] = how
    sets = {cond: set(solved[cond]) for cond in COND_DIR}
    inter = set.intersection(*sets.values()) if all(sets.values()) else set()
    print(f"\n===== {dom} =====")
    for cond in COND_DIR:
        print(f"  {cond:<11} solved {len(sets[cond])} distinct jsonl ids")
    print(f"  ALL-4 INTERSECTION (clean cells): n={len(inter)} -> {sorted(inter, key=int)}")
    # show strong-match coverage
    strong_cov = {cond: sum(1 for t in solved[cond] if conf[cond][t]=='strong') for cond in COND_DIR}
    print(f"  strong-anchor matches: {strong_cov}")
