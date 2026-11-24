"""Declarative oracle: warm A,B; issue C,A,B on independent IDs; B hits during C."""
import copy,json,subprocess,sys
r=subprocess.run([sys.argv[1]],capture_output=True,text=True,check=True);cases=[]
for line in r.stdout.splitlines():
 x=json.loads(line)
 if x['kind']=='case':cases.append([])
 else:cases[-1].append(x)
def check(rows):
 starts=[x for x in rows if x.get('action')=='sense-issue'];ends=[x for x in rows if x.get('action')=='sense-finish'];done=[x for x in rows if x['kind']=='complete']
 assert [x['page'] for x in starts]==[2,0] and [x['page'] for x in ends]==[2,0]
 assert all(b['ps']-a['ps']==2720000 for a,b in zip(starts,ends))
 assert [x['id'] for x in done]==[101,102,100]
 assert starts[0]['ps']<done[0]['ps']<ends[0]['ps'],'buffered B must finish while C senses'
 assert starts[1]['ps']>=ends[0]['ps']
for rows in cases:
 check(rows)
 for kind,field in [('complete','id'),('sense','page'),('sense','ps')]:
  bad=copy.deepcopy(rows);next(x for x in bad if x['kind']==kind)[field]+=1
  try:check(bad)
  except AssertionError:pass
  else:raise AssertionError('bad trace accepted')
assert len(cases)==2
print('PASS: two cache-overlap cases; six corrupt traces rejected')
