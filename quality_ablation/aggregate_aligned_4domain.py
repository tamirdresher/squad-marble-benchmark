"""Aggregate the FULL 4-domain aligned correctness/quality cells (research +
bargaining from the earlier aligned regrade, coding + database from the fresh
aligned rerun regrade) into per-condition tables.

All four domains are now clean same-task comparisons:
  - research (n=8), bargaining (n=10): alignment verified by rare-token anchors
  - coding (n=10), database (n=10): alignment guaranteed by construction
    (rerun_aligned_coding_db.py fed every condition the same jsonl task_id)

Milestone-KPI + 1-5 rubric, graded uniformly with the SAME Opus-4.6 judge/prompt/
gold across every condition. gpt-4o cross-check reported where prior aligned
scores exist (research/bargaining). Database gold blends diagnostic-process
milestones with one final-answer milestone -> its KPI is reported WITH a caveat,
and the uniform rubric is treated as the clean cross-domain correctness signal.
"""
import json, os
from collections import defaultdict

QA = os.path.dirname(os.path.abspath(__file__))
CELLS = os.path.join(QA, "aligned_cells")
CONDS = ["full_squad", "coord_only", "no_squad", "memory_only"]
ALIGNED = {"research":   ["1", "20", "40", "50", "60", "70", "80", "90"],
           "bargaining": ["1", "10", "20", "30", "40", "50", "60", "70", "80", "90"],
           "coding":     ["1", "10", "20", "30", "40", "50", "60", "70", "80", "90"],
           "database":   ["1", "10", "20", "30", "40", "50", "60", "70", "80", "90"]}
# database KPI mixes diagnostic-process milestones with one final-answer milestone
DB_CAVEAT = ("database gold blends process milestones (querying pg_stat_* views) with "
             "one final-answer milestone; treat its KPI as process-adherence and rely on "
             "the uniform 1-5 rubric for the clean correctness signal")

def load(cond, dom, slot):
    p = os.path.join(CELLS, cond, dom, f"task_{slot}.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None

agg = {}
for cond in CONDS:
    kpis = []; rubs = []; dom_k = defaultdict(list); dom_r = defaultdict(list)
    n_by_dom = {}
    for dom, slots in ALIGNED.items():
        got = 0
        for s in slots:
            c = load(cond, dom, s)
            if not c: continue
            got += 1
            kpis.append(c["kpi_rate"]); dom_k[dom].append(c["kpi_rate"])
            if c.get("rubric"):
                rubs.append(c["rubric"]["avg"]); dom_r[dom].append(c["rubric"]["avg"])
        n_by_dom[dom] = got
    agg[cond] = {
        "n": len(kpis),
        "n_by_domain": n_by_dom,
        "kpi_overall": round(100*sum(kpis)/len(kpis), 1) if kpis else None,
        "rubric_overall": round(sum(rubs)/len(rubs), 2) if rubs else None,
        "by_domain": {d: {"n": n_by_dom.get(d, 0),
                          "kpi": round(100*sum(dom_k[d])/len(dom_k[d]), 1) if dom_k[d] else None,
                          "rubric": round(sum(dom_r[d])/len(dom_r[d]), 2) if dom_r[d] else None}
                      for d in ALIGNED}
    }

print("=== FULL 4-DOMAIN aligned correctness/quality (Opus-4.6 uniform judge) ===")
hdr = f"{'cond':<12}{'n':>4}{'KPI%':>7}{'rub':>6}"
for d in ALIGNED: hdr += f"  {d[:4]}(K/r)".rjust(14)
print(hdr)
for c in CONDS:
    a = agg[c]; row = f"{c:<12}{a['n']:>4}{str(a['kpi_overall']):>7}{str(a['rubric_overall']):>6}"
    for d in ALIGNED:
        bd = a["by_domain"][d]; row += f"  {bd['kpi']}/{bd['rubric']}".rjust(14)
    print(row)
print(f"\nNOTE: {DB_CAVEAT}")

# gpt-4o cross-check (independent judge) where prior aligned scores exist
xmap = {"result_squad-copilot-cli": "full_squad", "result_coord-only": "coord_only",
        "result_no-squad-expanded": "no_squad", "result_memory-only": "memory_only"}
root = r"C:\Users\tamirdresher\source\repos\squad-marble-benchmark"
def cond_mean(entries, slots):
    v = [e["average"] for e in entries if str(e.get("task")) in slots]
    return round(sum(v)/len(v), 2) if v else None
gpt4o = {}
fp = os.path.join(root, "llm_judge_research_scores.json")
if os.path.exists(fp):
    d = json.load(open(fp, encoding="utf-8"))
    gpt4o["research"] = {xmap[k]: cond_mean(v.get("research", []), set(ALIGNED["research"]))
                         for k, v in d.items() if k in xmap}
fp = os.path.join(root, "llm_judge_bargaining_scores.json")
if os.path.exists(fp):
    d = json.load(open(fp, encoding="utf-8"))
    gpt4o["bargaining"] = {xmap[k]: cond_mean(v, set(ALIGNED["bargaining"]))
                           for k, v in d.items() if k in xmap}
print("\n=== JUDGE CROSS-CHECK: Opus(this run) vs gpt-4o(prior) rubric avg on aligned slots ===")
for dom in ("research", "bargaining"):
    if dom not in gpt4o: continue
    print(f"  [{dom}]")
    for c in CONDS:
        opus = agg[c]["by_domain"][dom]["rubric"]; g = gpt4o.get(dom, {}).get(c)
        print(f"    {c:<12} opus={opus}   gpt4o={g}")
print("  [coding/database] gpt-4o cross-check: run gpt4o_crosscheck_coding_db.py (optional) — "
      "Opus judge only in this table")

agg["_gpt4o_crosscheck"] = gpt4o
agg["_notes"] = {"database_kpi_caveat": DB_CAVEAT,
                 "alignment": "research/bargaining=anchor-verified; coding/database=by-construction (fresh aligned rerun)",
                 "judge": "claude-opus-4.6 uniform across all conditions & domains"}
json.dump(agg, open(os.path.join(QA, "aligned_quality_4domain.json"), "w", encoding="utf-8"), indent=2)
print("\nwrote aligned_quality_4domain.json")
