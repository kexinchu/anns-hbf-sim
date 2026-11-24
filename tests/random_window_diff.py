"""Independent scan implementation vs indexed scheduler: complete events and outputs."""
import pathlib,random,subprocess,sys,json,hashlib
old,new=map(lambda x:str(pathlib.Path(x).resolve()),sys.argv[1:3]);out=pathlib.Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
rng=random.Random(90421);spec=[]
for mode in ['service-v2','payload-v3']:
 for size,qd,pages,n in [(256,16,96,256),(4096,16,96,128),(256,1,2050,64)]:
  addresses=[(rng.choice([0,1024,2048]) if qd==1 else rng.randrange(pages))*4096 for _ in range(n)]
  spec.append(dict(mode=mode,size=size,qd=qd,pages=pages,addresses=addresses))
(out/'fixture.json').write_text(json.dumps(spec,indent=2));results=[]
def compare(a,b):
 assert a==b,"scan/index differential mismatch"
for i,s in enumerate(spec):
 obs=[];raw=''.join(f'{x}\n' for x in s['addresses'])
 for label,exe in [('scan',old),('index',new)]:
  r=subprocess.run([exe,str(s['size']),str(s['qd']),str(s['pages']),s['mode']],input=raw,text=True,capture_output=True,timeout=240)
  (out/f'{i}-{label}.jsonl').write_text(r.stdout);(out/f'{i}-{label}.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr;obs.append((r.stdout,r.stderr))
 compare(obs[0],obs[1])
 for bad in [(obs[0][0].replace('complete_ps','corrupted_ps',1),obs[0][1]),(obs[0][0],obs[0][1]+'bad digest')]:
  try:compare(obs[0],bad)
  except AssertionError:pass
  else:raise AssertionError('corrupt differential accepted')
 results.append({'case':i,'exact_events_completions_and_digest':True,'sha256':hashlib.sha256(obs[0][0].encode()).hexdigest()})
(out/'verdict.json').write_text(json.dumps({'cases':results,'mutations_rejected':12,'performance_ready':False},indent=2));print('PASS: six scan/index differentials')
