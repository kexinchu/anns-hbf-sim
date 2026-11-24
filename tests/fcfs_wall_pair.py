"""Paired host execution diagnostic; never treats wall time as device latency."""
import hashlib,json,pathlib,statistics,subprocess,sys,time
root=pathlib.Path(__file__).resolve().parents[1]
old=root/'calibration/paper-curves/final-20261123';new=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=False)
trace=(old/'4096-cold-sequential-independent.input').read_text()
expected=(old/'4096-cold-sequential-independent-q16.jsonl').read_text()
binaries={'baseline':pathlib.Path(sys.argv[3]) if len(sys.argv)>3 else old/'probe.bin','optimized':new};rows=[]
for label in ['baseline','optimized','optimized','baseline','optimized','baseline','baseline','optimized']:
 start=time.monotonic();r=subprocess.run([str(binaries[label].resolve()),'4096','16','0','0'],input=trace,capture_output=True,text=True,timeout=180)
 elapsed=time.monotonic()-start
 assert r.returncode==0 and r.stdout==expected,(label,r.stderr)
 rows.append({'label':label,'wall_seconds':elapsed,'stdout_sha256':hashlib.sha256(r.stdout.encode()).hexdigest()})
 (out/'runs.json').write_text(json.dumps(rows,indent=2));print(label,elapsed,flush=True)
med={k:statistics.median(x['wall_seconds'] for x in rows if x['label']==k) for k in binaries}
(out/'verdict.json').write_text(json.dumps({'case':'4096-cold-sequential-independent-q16','binary_sha256':{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in binaries.items()},'median_wall_seconds':med,'host_execution_speedup':med['baseline']/med['optimized'],'scope':'paired local wall time, one fixture; not simulated hardware speedup','performance_ready':False},indent=2))
