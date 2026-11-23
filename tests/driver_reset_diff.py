"""Independent observable contract oracle; no simulator imports or state helpers."""
import json, pathlib, subprocess, sys
exe=str(pathlib.Path(sys.argv[1]).resolve()); out=pathlib.Path(sys.argv[2]); out.mkdir(parents=True,exist_ok=True)
phases=['handoff','rx-arrival','accepted','erase-issue','program-issue','program-finish','egress-ready','response-issue','delivered','sense-issue','window-release','cache-hit']
value=((11*0x9e3779b97f4a7c15)&((1<<64)-1))%97+20
expected=[sum((value+(k*32+j)%17-3)**2 for j in range(32)) for k in range(32)]
def run(p,k,mutation=''):
 args=[exe,p,k]+([mutation] if mutation else [])
 r=subprocess.run(args,capture_output=True,text=True,timeout=30)
 stem=out/(p+'-'+k+('-'+mutation if mutation else ''))
 stem.with_suffix('.stdout').write_text(r.stdout); stem.with_suffix('.stderr').write_text(r.stderr)
 stem.with_suffix('.run.json').write_text(json.dumps({'args':args,'exit':r.returncode}))
 return r

def check(r,p,k):
 assert r.returncode==0, r.stderr
 rows=[json.loads(x) for x in r.stdout.splitlines()]
 completions={x['completion']:x['success'] for x in rows if 'completion' in x}
 assert completions[100] is False
 if p not in phases[9:]: assert completions[101] is False
 if p in phases[9:] and k=='die': assert completions[150] and completions[151]
 uncertain=p in phases[:5]
 state=next(x for x in rows if 'unknown' in x)
 assert state=={'unknown':uncertain,'ready':1},state
 assert completions[200] == (not uncertain)
 assert all(completions[x] for x in [300,301,400])
 for tag in ['drained','final']:
  a=next(x for x in rows if x.get('event')==tag)
  assert a['resources']==[0]*16,(tag,a)
  assert a['handed']==a['accepted']==a['responses'] and a['errors']>0
 a=next(x for x in rows if x.get('event')=='at_reset')
 stage_resources={'handoff':[1,2], 'rx-arrival':[1], 'accepted':[3,4],
  'erase-issue':[5], 'program-issue':[5], 'program-finish':[3],
  'egress-ready':[9], 'response-issue':[10], 'delivered':[11],
  'sense-issue':[5,13], 'window-release':[8], 'cache-hit':[12]}
 assert all(a['resources'][i]>0 for i in stage_resources[p]),(p,a)
 data=next(x for x in rows if 'scores' in x)
 assert data['physical']==[0,0,0,0,0]
 assert data['scores']==expected,'distance mismatch'
for p in phases:
 for k in ['warm','power','die']: check(run(p,k),p,k)
r=run('program-issue','warm','publish_unknown')
assert r.returncode!=0 and 'unknown publication' in r.stderr
r=run('program-issue','warm','bad_score')
assert r.returncode==0
try: check(r,'program-issue','warm')
except AssertionError as e: assert str(e)=='distance mismatch'
else: raise AssertionError('score mutation escaped independent oracle')
print('PASS: 36 full-driver schedules; 2 negative mutations; independent data, completion, uncertainty and resource checks')
