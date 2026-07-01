import json, os
QA = os.path.dirname(os.path.abspath(__file__))
HEAD, TAIL = 3000, 8000
for cond in ['full_squad', 'no_squad']:
    print('---', cond, 'coding ---')
    for t in ['1','10','20','30','40','50','60','70','80','90']:
        d = json.load(open(os.path.join(QA,'cells',cond,'coding',f'task_{t}.json')))
        L = d['raw_len']
        windowed = 'WIN' if L > HEAD+TAIL else 'full'
        rub = (d.get('rubric') or {}).get('avg')
        print(f'  t{t:<3} kpi={d["kpi_rate"]:.2f} len={L:<6} {windowed} rubric={rub}')
