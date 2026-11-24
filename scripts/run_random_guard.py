import concurrent.futures,gzip,hashlib,json,pathlib,subprocess,sys,time
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tests'))
from turnover_v3 import trace
exe=str(pathlib.Path(sys.argv[1]).resolve());out=pathlib.Path(sys.argv[2]);out.mkdir(exist_ok=False,parents=True)
p=root/'calibration/random-window-v1/protocol.json';assert hashlib.sha256(p.read_bytes()).hexdigest()==p.with_suffix('.sha256').read_text().split()[0]
(out/'manifest.json').write_text(json.dumps({'binary_sha256':hashlib.sha256(pathlib.Path(exe).read_bytes()).hexdigest(),'protocol_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'fit_performed':False},indent=2))
def run(job):
 mode,size=job;key=f'{mode}-{size}';a=trace(size,3072,'random');a+=a[:128];raw=''.join(f'{x}\n' for x in a);t=time.monotonic()
 with gzip.open(out/(key+'.input.gz'),'wt') as f:f.write(raw)
 r=subprocess.run([exe,str(size),'128','3072',mode],input=raw,text=True,capture_output=True,timeout=1800)
 with gzip.open(out/(key+'.jsonl.gz'),'wt') as f:f.write(r.stdout)
 (out/(key+'.stderr')).write_text(r.stderr);(out/(key+'.status.json')).write_text(json.dumps({'exit':r.returncode,'wall_seconds':time.monotonic()-t}));assert r.returncode==0,r.stderr
 print(key,'completed',flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(run,[(m,s) for m in ['service-v2','payload-v3'] for s in [256,4096]]))
