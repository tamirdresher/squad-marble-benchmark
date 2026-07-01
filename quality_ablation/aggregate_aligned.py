"""Aggregate the aligned correctness/quality cells into per-condition tables and
cross-check the milestone-KPI ranking against the pre-existing gpt-4o rubric
scores (independent judge, bias sanity check)."""
import json, os
from collections import defaultdict

QA = os.path.dirname(os.path.abspath(__file__))
CELLS = os.path.join(QA, "aligned_cells")
CONDS = ["full_squad","coord_only","no_squad","memory_only"]
ALIGNED = {"research": ["1","20","40","50","60","70","80","90"],
           "bargaining": ["1","10","20","30","40","50","60","70","80","90"]}

def load(cond,dom,slot):
    p=os.path.join(CELLS,cond,dom,f"task_{slot}.json")
    return json.load(open(p,encoding="utf-8")) if os.path.exists(p) else None

agg={}
per_dom=defaultdict(dict)
for cond in CONDS:
    kpis=[]; rubs=[]; dom_k=defaultdict(list); dom_r=defaultdict(list)
    for dom,slots in ALIGNED.items():
        for s in slots:
            c=load(cond,dom,s)
            if not c: continue
            kpis.append(c["kpi_rate"]); dom_k[dom].append(c["kpi_rate"])
            if c.get("rubric"):
                rubs.append(c["rubric"]["avg"]); dom_r[dom].append(c["rubric"]["avg"])
    agg[cond]={
        "n":len(kpis),
        "kpi_overall":round(100*sum(kpis)/len(kpis),1) if kpis else None,
        "rubric_overall":round(sum(rubs)/len(rubs),2) if rubs else None,
        "by_domain":{d:{"kpi":round(100*sum(dom_k[d])/len(dom_k[d]),1),
                        "rubric":round(sum(dom_r[d])/len(dom_r[d]),2) if dom_r[d] else None}
                     for d in ALIGNED}
    }

print("=== ALIGNED correctness/quality (research n=8 + bargaining n=10) ===")
print(f"{'cond':<12}{'n':>4}{'KPI%':>8}{'rubric':>8}   research(KPI/rub)   bargaining(KPI/rub)")
for c in CONDS:
    a=agg[c]; rd=a["by_domain"]["research"]; bd=a["by_domain"]["bargaining"]
    print(f"{c:<12}{a['n']:>4}{a['kpi_overall']:>8}{a['rubric_overall']:>8}   "
          f"{rd['kpi']}/{rd['rubric']}          {bd['kpi']}/{bd['rubric']}")

# cross-check vs existing gpt-4o rubric scores (independent judge) on SAME aligned slots
xmap={"result_squad-copilot-cli":"full_squad","result_coord-only":"coord_only",
      "result_no-squad-expanded":"no_squad","result_memory-only":"memory_only"}
root=r"C:\Users\tamirdresher\source\repos\squad-marble-benchmark"
def cond_mean(entries, slots):
    v=[e["average"] for e in entries if str(e.get("task")) in slots]
    return round(sum(v)/len(v),2) if v else None
gpt4o={}
# research: {cond:{research:[...]}}
fp=os.path.join(root,"llm_judge_research_scores.json")
if os.path.exists(fp):
    d=json.load(open(fp,encoding="utf-8"))
    gpt4o["research"]={xmap[k]:cond_mean(v.get("research",[]),set(ALIGNED["research"]))
                       for k,v in d.items() if k in xmap}
# bargaining: {cond:[...]}
fp=os.path.join(root,"llm_judge_bargaining_scores.json")
if os.path.exists(fp):
    d=json.load(open(fp,encoding="utf-8"))
    gpt4o["bargaining"]={xmap[k]:cond_mean(v,set(ALIGNED["bargaining"]))
                         for k,v in d.items() if k in xmap}
print("\n=== JUDGE CROSS-CHECK: Opus(this run) vs gpt-4o(prior) rubric avg on aligned slots ===")
for dom in ALIGNED:
    print(f"  [{dom}]")
    for c in CONDS:
        opus=agg[c]["by_domain"][dom]["rubric"]
        g=gpt4o.get(dom,{}).get(c)
        print(f"    {c:<12} opus={opus}   gpt4o={g}")
agg["_gpt4o_crosscheck"]=gpt4o

json.dump(agg,open(os.path.join(QA,"aligned_quality_results.json"),"w",encoding="utf-8"),indent=2)
print("\nwrote aligned_quality_results.json")
