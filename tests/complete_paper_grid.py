"""Complete missing frozen points with bounded wall budgets; never impute failures."""
import concurrent.futures,csv,hashlib,itertools,json,pathlib,random,shutil,subprocess,sys
from paper_curve_audit import check
root=pathlib.Path(__file__).resolve().parents[1];out=pathlib.Path(sys.argv[2]);exe=pathlib.Path(sys.argv[1])
manifest=json.loads((out/'manifest.json').read_text());protocol=root/'calibration/paper-curves/protocol.json'
assert hashlib.sha256(protocol.read_bytes()).hexdigest()==manifest['protocol_sha256']
assert hashlib.sha256(exe.read_bytes()).hexdigest()==manifest['binary_sha256']
snapshot=out/'probe.bin'
if not snapshot.exists():shutil.copy2(exe,snapshot)
assert hashlib.sha256(snapshot.read_bytes()).hexdigest()==manifest['binary_sha256']
snapshot=snapshot.resolve();v=json.loads(protocol.read_text())['validation']
(out/'continuation.json').write_text(json.dumps({'workers':4,'wall_timeout_seconds':180,'purpose':'complete missing grid points without model changes','runner_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()},indent=2))
def run(point):
 size,cache,access,dep,qd=point;name=f'{size}-{cache}-{access}-{dep}';key=f'{name}-q{qd}';raw=out/(key+'.jsonl')
 args=(size,qd,cache=='hot',dep=='chain')
 pages=list(range(1024))
 if access=='permutation':random.Random(1729).shuffle(pages)
 trace='\n'.join(map(str,pages))+'\n';(out/(name+'.input')).write_text(trace)
 if not raw.exists():
  try:r=subprocess.run([str(snapshot),str(size),str(qd),str(int(args[2])),str(int(args[3]))],input=trace,capture_output=True,text=True,timeout=180)
  except subprocess.TimeoutExpired as e:
   (out/(key+'.partial')).write_bytes(e.stdout or b'');(out/(key+'.stderr')).write_bytes(e.stderr or b'')
   (out/(key+'.invalid.json')).write_text(json.dumps({'valid':False,'reason':'host wall timeout','seconds':180}))
   return dict(case=name,qd=qd,status='HOST_TIMEOUT',elapsed_ps='',GBps='',p99_ps='',senses='',paper_GBps='',relative_error_to_paper='unavailable')
  raw.write_text(r.stdout);(out/(key+'.stderr')).write_text(r.stderr)
  if r.returncode:raise RuntimeError((key,r.returncode,r.stderr))
 records=[json.loads(x) for x in raw.read_text().splitlines()];check(records,*args);s=records[-1];lat=sorted(r['complete_ps']-r['submit_ps'] for r in records[:-1])
 return dict(case=name,qd=qd,status='CHECKED',elapsed_ps=s['elapsed_ps'],GBps=s['useful_bytes']*1000/s['elapsed_ps'],p99_ps=lat[1013],senses=s['senses'],paper_GBps='',relative_error_to_paper='unavailable')
points=list(itertools.product(v['sizes'],v['cache'],v['access'],v['dependency'],v['qd']))
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 futures={pool.submit(run,p):p for p in points}
 for f in concurrent.futures.as_completed(futures):
  r=f.result();rows.append(r);print(r['case'],r['qd'],r['status'],flush=True)
rows.sort(key=lambda r:(r['case'],r['qd']))
with (out/'curves.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
for name in {r['case'] for r in rows if r['case'].endswith('chain')}:
 assert len({r['elapsed_ps'] for r in rows if r['case']==name and r['status']=='CHECKED'})==1
(out/'verdict.json').write_text(json.dumps({'grid_points':len(rows),'checked':sum(r['status']=='CHECKED' for r in rows),'invalid':sum(r['status']!='CHECKED' for r in rows),'paper_curve_reproduced':False,'hardware_calibrated':False,'performance_ready':False},indent=2))
