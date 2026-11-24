"""Same frozen model, same traces; byte-exact old outputs and wall-time accounting."""
import csv,hashlib,itertools,json,pathlib,random,shutil,subprocess,sys,time
from paper_curve_audit import check
root=pathlib.Path(__file__).resolve().parents[1];protocol=root/'calibration/paper-curves/protocol.json'
old=root/'calibration/paper-curves/final-20261123';out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=False)
shutil.copy2(sys.argv[1],out/'probe.bin');exe=(out/'probe.bin').resolve();cfg=json.loads(protocol.read_text());v=cfg['validation']
(out/'manifest.json').write_text(json.dumps({'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'binary_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'comparison':'unchanged frozen inputs; original completed outputs byte-for-byte','sources':{s:hashlib.sha256((root/s).read_bytes()).hexdigest() for s in ['scripts/fcfs_index_overlay.py','scripts/prepare_eventlab.py','src/paper_curve_probe.cpp','tests/fcfs_curve_replay.py']}},indent=2))
rows=[];matched=0
for size,cache,access,dep,qd in itertools.product(v['sizes'],v['cache'],v['access'],v['dependency'],v['qd']):
 name=f'{size}-{cache}-{access}-{dep}';key=f'{name}-q{qd}';trace=(old/(name+'.input')).read_text()
 begin=time.monotonic()
 try:r=subprocess.run([str(exe),str(size),str(qd),str(int(cache=='hot')),str(int(dep=='chain'))],input=trace,text=True,capture_output=True,timeout=180)
 except subprocess.TimeoutExpired as e:
  (out/(key+'.partial')).write_bytes(e.stdout or b'');raise
 seconds=time.monotonic()-begin
 (out/(key+'.jsonl')).write_text(r.stdout);(out/(key+'.stderr')).write_text(r.stderr)
 assert r.returncode==0,(key,r.stderr)
 data=[json.loads(x) for x in r.stdout.splitlines()];check(data,size,qd,cache=='hot',dep=='chain');s=data[-1]
 if (old/(key+'.jsonl')).exists():
  assert r.stdout==(old/(key+'.jsonl')).read_text(),('virtual trace changed',key)
  matched+=1
 lat=sorted(x['complete_ps']-x['submit_ps'] for x in data[:-1])
 rows.append(dict(case=name,qd=qd,status='CHECKED',elapsed_ps=s['elapsed_ps'],GBps=s['useful_bytes']*1000/s['elapsed_ps'],p99_ps=lat[1013],senses=s['senses'],host_wall_seconds=seconds,paper_GBps='',relative_error_to_paper='unavailable'))
 print(key,round(seconds,3),'host seconds',flush=True)
with (out/'curves.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
(out/'verdict.json').write_text(json.dumps({'completed':len(rows),'old_completed_traces_exact':matched,'newly_completed':len(rows)-matched,'performance_ready':False,'hardware_calibrated':False,'paper_curve_reproduced':False},indent=2))
