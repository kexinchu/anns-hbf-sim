"""Independent integer timing/byte oracle for actual DeviceDriver trace events."""
import json,pathlib,subprocess,sys,copy
exe=str(pathlib.Path(sys.argv[1]).resolve());out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
r=subprocess.run([exe],capture_output=True,text=True,timeout=30);(out/'trace.jsonl').write_text(r.stdout);(out/'stderr.txt').write_text(r.stderr);assert r.returncode==0,r.stderr
cases=[]
for line in r.stdout.splitlines():
 x=json.loads(line)
 if x['kind']=='case':cases.append([x,[]])
 elif x['kind']=='event':cases[-1][1].append(x)
def check(cfg,events):
 rate={1:48,2:94,3:188}[cfg['grade']];req=(16000+rate-1)//rate;resp=((64+cfg['response_control'])*1000+rate-1)//rate
 if len(sys.argv)>3 and sys.argv[3]=='v3':
  raw={1:64,2:128,3:256}[cfg['grade']];req=(16000+raw-1)//raw;resp=(64000+rate-1)//rate
 by={}
 for e in events:by.setdefault((e['channel'],e['id']),{})[e['action']]=e['ps']
 assert len(by)==128 and not any(e['action'].startswith('sense-') for e in events)
 for x in by.values():
  assert x['rx-arrival']-x['handoff']==req+cfg['fixed_ps'],'request accounting'
  assert x['delivered']-x['response-issue']==resp+cfg['fixed_ps'],'response accounting'
 for ch in range(2):
  ts=[x['response-issue'] for (c,_),x in by.items() if c==ch];ts.sort();assert len(ts)==64
  assert all(b-a==resp for a,b in zip(ts,ts[1:])), 'saturated serialization lane'
  assert max(x['delivered'] for (c,_),x in by.items() if c==ch)-ts[0]==64*resp+cfg['fixed_ps'], 'payload service ceiling'
 # With these two symmetric channels the return streams overlap, not one cube-wide lane.
 first=[min(x['response-issue'] for (c,_),x in by.items() if c==ch) for ch in range(2)];assert first[0]==first[1]
for c,e in cases:check(c,e)
assert len(cases)==12
bad=copy.deepcopy(cases[0]);next(e for e in bad[1] if e['action']=='delivered')['ps']+=1
mutants=[bad,[dict(cases[0][0],grade=2),cases[0][1]],[dict(cases[0][0],fixed_ps=100),cases[0][1]]]
for c,e in mutants:
 try:check(c,e)
 except AssertionError:pass
 else:raise AssertionError('corrupted accounting accepted')
(out/'verdict.json').write_text(json.dumps({'model':'payload-v3' if len(sys.argv)>3 and sys.argv[3]=='v3' else 'service-v2','cases':12,'read_commands':1536,'negative_cases':3,'checks':'PASS','scope':'transaction-level service accounting, NOT flit calibration','hardware_calibrated':False},indent=2));print('PASS: 12 cases, 1536 read commands, 3 negative controls')
