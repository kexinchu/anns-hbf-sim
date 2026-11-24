"""Reject protocol/arrival/evidence corruption using a preserved original-scanner fixture."""
import copy,json,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from paper_curves_v2 import cases,addresses,validate,ROOT
cfg=json.loads((ROOT/'calibration/paper-curves/protocol-v2.json').read_text());grid=cases(cfg)
assert len(grid)==192 and len({tuple(c.items()) for c in grid})==192
c=dict(size=256,cache='cold',pattern='random',qd=1024,mocs=4096,seed=8301)
p=ROOT/'calibration/large-window-fix/20261124/release-differential';raw=(p/'cold-wide-scan.jsonl').read_text();err=(p/'cold-wide-scan.stderr').read_text();addr=addresses(c);validate(c,addr,raw,err)
rows=[json.loads(x) for x in raw.splitlines()]
bad=[]
x=copy.deepcopy(rows);x[0]['submit_ps']=1;bad.append(x)
x=copy.deepcopy(rows);x[0]['id']=x[1]['id'];bad.append(x)
x=copy.deepcopy(rows);x[-1]['senses']=64;bad.append(x)
x=copy.deepcopy(rows);x[-1]['useful_bytes']*=2;bad.append(x)
x=copy.deepcopy(rows);x[-1]['elapsed_ps']-=1;bad.append(x)
for x in bad:
 try:validate(c,addr,'\n'.join(map(json.dumps,x)),err)
 except AssertionError:pass
 else:raise AssertionError('corrupt curve accepted')
assert len(set(a//4096 for a in addresses(dict(c,pattern='sequential'))))==64
assert addresses(c)!=addresses(dict(c,seed=2718))
print('PASS: frozen 192-point grid, original-scanner fixture, 5 corrupted records rejected')
