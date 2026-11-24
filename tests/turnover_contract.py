"""Independent two-entry FIFO oracle, quiescent dependent reads on one bank."""
import json,random,subprocess,sys
exe=sys.argv[1]
rng=random.Random(9031)
sequence=[0,1,0,2,0,1,2,1]+[rng.randrange(3) for _ in range(128)]
cache=[];expected=[]
for p in sequence:
 if p not in cache:
  expected.append(p)
  if len(cache)==2:cache.pop(0)
  cache.append(p)
def audit(rows):
 issues=[r for r in rows if r.get('action')=='sense-issue']
 finishes=[r for r in rows if r.get('action')=='sense-finish']
 assert [r['page'] for r in issues]==expected
 assert len(finishes)==len(issues)
 assert all(a['bank']==b['bank']==0 and a['id']==b['id'] and a['page']==b['page'] and b['ps']-a['ps']==2720000 for a,b in zip(issues,finishes))
 requests=[r for r in rows if r['kind']=='request']
 assert len(requests)==len(sequence)
 assert requests[0]['submit_ps']==0
 assert all(b['submit_ps']==a['complete_ps'] for a,b in zip(requests,requests[1:]))
 assert rows[-1]['senses']==len(expected)
for mode in ['service-v2','payload-v3']:
 r=subprocess.run([exe,'256','1','3072',mode],input=''.join(f'{p*4194304}\n' for p in sequence),text=True,capture_output=True,check=True)
 rows=[json.loads(l) for l in r.stdout.splitlines()];audit(rows)
 for field in ['page','ps','id']:
  bad=[dict(r) for r in rows];next(r for r in bad if r.get('action')=='sense-finish')[field]+=1
  try:audit(bad)
  except AssertionError:pass
  else:raise AssertionError('accepted corrupted sense')
for args,raw in [(['256','0','3072','payload-v3'],'0\n'),(['256','1','3072','bad'],'0\n'),(['256','1','3072','payload-v3'],'1\n'),(['256','1','3072','payload-v3'],'12582912\n')]:
 assert subprocess.run([exe,*args],input=raw,text=True,capture_output=True).returncode!=0
print('two independent FIFO traces passed; six corrupt traces and four invalid inputs rejected')
