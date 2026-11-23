"""Frozen diagnostic grid; never fits parameters or invents paper observations."""
import hashlib,itertools,json,pathlib,random,subprocess,sys,csv,shutil
root=pathlib.Path(__file__).resolve().parents[1]
protocol=root/'calibration/paper-curves/protocol.json'
cfg=json.loads(protocol.read_text());v=cfg['validation']
exe=pathlib.Path(sys.argv[1]).resolve();out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=False)
shutil.copy2(exe,out/"probe.bin");exe=(out/"probe.bin").resolve()
manifest={'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'binary_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'sources':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['src/paper_curve_probe.cpp','tests/paper_curves.py']}}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
rows=[]
for size,cache,access,dep in itertools.product(v['sizes'],v['cache'],v['access'],v['dependency']):
 pages=list(range(v['footprint_pages']))
 if access=='permutation': random.Random(v['seeds'][0]).shuffle(pages)
 trace='\n'.join(map(str,pages))+'\n';name=f'{size}-{cache}-{access}-{dep}'
 (out/(name+'.input')).write_text(trace)
 for qd in v['qd']:
  key=f'{name}-q{qd}'
  try:
   r=subprocess.run([str(exe),str(size),str(qd),str(int(cache=='hot')),str(int(dep=='chain'))],input=trace,text=True,capture_output=True,timeout=180)
  except subprocess.TimeoutExpired as error:
   (out/(key+'.timeout.json')).write_text(json.dumps({'valid':False,'timeout_seconds':180}))
   (out/(key+'.partial')).write_bytes(error.stdout or b'')
   (out/(key+'.stderr')).write_bytes(error.stderr or b'')
   raise
  (out/(key+'.jsonl')).write_text(r.stdout);(out/(key+'.stderr')).write_text(r.stderr)
  assert r.returncode==0,(key,r.returncode,r.stderr)
  data=[json.loads(x) for x in r.stdout.splitlines()];s=data[-1];requests=data[:-1]
  assert len(requests)==1024 and len({x['id'] for x in requests})==1024
  assert s['requests']==1024 and s['senses']==(0 if cache=='hot' else 1024),s
  assert s['peak']==(1 if dep=='chain' else qd)
  assert all(x['complete_ps']>=x['submit_ps'] for x in requests)
  bw=s['useful_bytes']*1000/s['elapsed_ps']
  assert bw<=1504,'exceeds aggregate payload upper bound'
  if cache=='cold':assert s['elapsed_ps']>=cfg['sense_ps']
  if dep=='chain' and cache=='cold':assert s['elapsed_ps']>=1024*cfg['sense_ps']
  lat=sorted(x['complete_ps']-x['submit_ps'] for x in requests)
  rows.append(dict(case=name,qd=qd,elapsed_ps=s['elapsed_ps'],GBps=bw,p99_ps=lat[1013],senses=s['senses'],paper_GBps='',relative_error_to_paper='unavailable'))
  print(key,round(bw,4),'GB/s model',flush=True)
for name in {r['case'] for r in rows if r['case'].endswith('chain')}:
 assert len({r['elapsed_ps'] for r in rows if r['case']==name})==1,'dependency chain changed with ineffective QD'
with (out/'curves.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(out/'verdict.json').write_text(json.dumps({'cases':len(rows),'checks':'PASS','paper_curve_reproduced':False,'hardware_calibrated':False,'performance_ready':False},indent=2))
