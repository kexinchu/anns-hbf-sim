import sys,pathlib,subprocess,gzip,json,hashlib,time
sys.path.insert(0,'tests')
from turnover_v3 import trace,check
out=pathlib.Path('retry-input-limit');out.mkdir(exist_ok=False)
exe='./turnover_probe_limit'
(out/'manifest.json').write_text(json.dumps({'binary_sha256':hashlib.sha256(pathlib.Path(exe).read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(pathlib.Path('src/turnover_probe.cpp').read_bytes()).hexdigest(),'max_logical_fragments':2097152,'fit_performed':False},indent=2))
results=[]
for size in [256,4096]:
 key=f'payload-v3-{size}-6144-sequential';a=trace(size,6144,'sequential');raw=''.join(f'{x}\n' for x in a);t=time.monotonic()
 with gzip.open(out/(key+'.input.gz'),'wt') as f:f.write(raw)
 r=subprocess.run([exe,str(size),'128','6144','payload-v3'],input=raw,text=True,capture_output=True,timeout=1800)
 with gzip.open(out/(key+'.jsonl.gz'),'wt') as f:f.write(r.stdout)
 (out/(key+'.stderr')).write_text(r.stderr)
 (out/(key+'.status.json')).write_text(json.dumps({'exit':r.returncode,'wall_seconds':time.monotonic()-t}))
 assert r.returncode==0,r.stderr
 result=check(r.stdout,a,size,128,6144);result.update(mode='payload-v3',size=size,pages=6144,pattern='sequential',qd=128);results.append(result);print(result,flush=True)
(out/'summary.json').write_text(json.dumps(results,indent=2))
