"""Validate complete traces independently before extracting model diagnostics."""
import json,pathlib,re
root=pathlib.Path(__file__).resolve().parent
results=[]
for folder in ['on','qd128']:
 statuses=json.loads((root/folder/'status.json').read_text())
 for s in statuses:
  if s.get('exit')!=0:continue
  m=s['mocs'];rows=[json.loads(x) for x in (root/folder/f'mocs-{m}.jsonl').read_text().splitlines()]
  assert len(rows)==1025
  summary=rows[-1];req=rows[:-1];assert summary['kind']=='summary' and all(x['kind']=='request' for x in req)
  assert sorted(x['id'] for x in req)==list(range(10000,11024))
  assert summary['requests']==summary['senses']==1024 and summary['useful_bytes']==4194304
  assert summary['hot']==0 and summary['dependent']==0
  assert min(x['submit_ps'] for x in req)==0
  assert max(x['complete_ps'] for x in req)==summary['elapsed_ps']
  assert all(x['complete_ps']-x['submit_ps']>=2720000 for x in req)
  # Independent reconstruction of logical outstanding requests from timestamps.
  timeline=[]
  for x in req:timeline.extend([(x['submit_ps'],1),(x['complete_ps'],-1)])
  active=peak=0
  for t,delta in sorted(timeline):
   active+=delta;assert active>=0;peak=max(peak,active)
  assert active==0 and peak==summary['peak']==summary['qd']
  match=re.search(r'peak_busy_banks=(\d+) remaining=0 mocs='+str(m),(root/folder/f'mocs-{m}.stderr').read_text());assert match
  busy=int(match[1]);assert 1<=busy<=1024
  results.append(dict(qd=summary['qd'],mocs=m,peak_busy_banks=busy,elapsed_ps=summary['elapsed_ps'],modeled_GBps=summary['useful_bytes']*1000/summary['elapsed_ps']))
(root/'results.json').write_text(json.dumps({'complete_runs':results,'performance_ready':False,'hardware_calibrated':False,'paper_curve_reproduced':False},indent=2))
print(results)
