import json, os
QA = os.path.dirname(os.path.abspath(__file__))
WT = (r"C:\Users\tamirdresher\.copilot\repos\copilot-worktrees\tamresearch1"
      r"\tamirdresher-microsoft-fluffy-dollop\squad-marble\results")

g = json.load(open(os.path.join(QA, 'gold', 'database', 'task_10.json')))
print('=== database GOLD milestones task 10 ===')
for i, m in enumerate(g['milestones']):
    print(f'  {i+1}. {m}')
print()

for cond, dirn in [('full_squad', 'result_squad-copilot-cli'), ('no_squad', 'result_no-squad-expanded')]:
    p = os.path.join(WT, dirn, 'database', 'task_10.json')
    d = json.load(open(p, encoding='utf-8-sig'))
    o = d.get('output') or d.get('final_output') or ''
    c = json.load(open(os.path.join(QA, 'cells', cond, 'database', 'task_10.json')))
    print(f'=== {cond} db t10 len={len(o)} kpi={c["kpi_rate"]} achieved={c["kpi_achieved"]} ===')
    print(o[:500])
    print('   ...TAIL...')
    print(o[-350:])
    print()
