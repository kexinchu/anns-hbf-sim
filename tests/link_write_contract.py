"""Independent payload-request and control-only ACK timing oracle."""
import json,subprocess,sys,copy
r=subprocess.run([sys.argv[1]],capture_output=True,text=True,check=True);cases=[]
for line in r.stdout.splitlines():
 x=json.loads(line)
 if x['kind']=='case':cases.append((x,[]))
 else:cases[-1][1].append(x)
def check(c,events):
 eff={1:48,2:94,3:188}[c['grade']];raw={1:64,2:128,3:256}[c['grade']]
 req=((4096+(0 if c['payload'] else c['control']))*1000+eff-1)//eff
 ack_rate=raw if c['payload'] else eff;ack=(c['control']*1000+ack_rate-1)//ack_rate
 by={}
 for e in events:
  if e['action'] in ['handoff','rx-arrival','response-issue','delivered']:by.setdefault((e['channel'],e['id']),{})[e['action']]=e['ps']
 assert len(by)==4
 for t in by.values():
  assert t['rx-arrival']-t['handoff']==req+100
  assert t['delivered']-t['response-issue']==ack+100
for c,e in cases:
 check(c,e)
 for action in ['rx-arrival','delivered']:
  bad=copy.deepcopy(e);next(x for x in bad if x['action']==action)['ps']+=1
  try:check(c,bad)
  except AssertionError:pass
  else:raise AssertionError('corrupt timing accepted')
assert len(cases)==12
print('12 write/ACK cases passed; 24 timing mutations rejected')
