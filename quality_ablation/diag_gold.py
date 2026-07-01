import json, os
QA = os.path.dirname(os.path.abspath(__file__))
for dom in ['coding', 'research', 'bargaining', 'database']:
    g = json.load(open(os.path.join(QA, 'gold', dom, 'task_10.json')))
    print(f'=== {dom} gold milestones (task 10) ===')
    for i, m in enumerate(g['milestones']):
        print(f'  {i+1}. {m}')
    print()
