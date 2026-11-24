"""Predeclared long-workset runs; stability is an observation, never a fitted criterion."""
import concurrent.futures,csv,gzip,hashlib,json,math,pathlib,random,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
def trace(size,pages,pattern):
 a=list(range(pages));random.Random(314159).shuffle(a)
 if pattern=='sequential':return list(range(0,pages*4096,size))*4
 return [p*4096 for p in a]*4

def check(data,addrs,size,qd,pages):
 rows=[json.loads(l) for l in data.splitlines()];req=[x for x in rows if x['kind']=='request'];events=[x for x in rows if x['kind']=='sense'];s=rows[-1];n=len(addrs)
 assert len(req)==n and {r['id'] for r in req}==set(range(10000,10000+n));by={r['id']-10000:r for r in req}
 assert all(by[i]['submit_ps']==0 for i in range(min(n,qd)))
 assert all(by[i]['submit_ps']==req[i-qd]['complete_ps'] for i in range(qd,n))
 assert all(x['complete_ps']>=x['submit_ps'] for x in req)
 assert s['requests']==n and s['useful_bytes']==n*size and s['elapsed_ps']==req[-1]['complete_ps']
 live={};seen={};issues=0
 for e in events:
  if e['action']=='sense-issue':
   assert e['bank'] not in live,'overlapping bank senses';live[e['bank']]=e;issues+=1;seen.setdefault(e['bank'],set()).add(e['page'])
  else:
   a=live.pop(e['bank']);assert e['id']==a['id'] and e['page']==a['page'] and e['ps']-a['ps']==2720000
 assert not live and issues==s['senses']
 assert len(seen)==1024 and all(len(v)>=pages//1024 for v in seen.values()),'no actual page turnover'
 win=n//4;last=0;rates=[];lat=[]
 for k in range(4):
  rr=req[k*win:(k+1)*win];end=rr[-1]['complete_ps'];rates.append(win*size*1000/(end-last));last=end
  vals=sorted(r['complete_ps']-r['submit_ps'] for r in rr);lat.append(vals[math.ceil(.99*win)-1])
 return dict(requests=n,senses=issues,page_efficiency=n*size/(issues*4096),window_GBps=rates,window_p99_ps=lat,steady=max(rates[1:])/min(rates[1:])<=1.05,distinct_banks=len(seen),min_pages_per_bank=min(map(len,seen.values())))
def main():
 exe=str(pathlib.Path(sys.argv[1]).resolve());out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=False)
 proto=ROOT/'calibration/turnover-v3/protocol.json';assert hashlib.sha256(proto.read_bytes()).hexdigest()==proto.with_suffix('.sha256').read_text().split()[0]
 jobs=[(mode,size,3072,pat,1 if pat=='dependent' else 128) for mode in ['service-v2','payload-v3'] for size,pat in [(256,'sequential'),(4096,'sequential'),(256,'random'),(4096,'random'),(256,'dependent')]]+ [('payload-v3',s,6144,'sequential',128) for s in [256,4096]]
 (out/'manifest.json').write_text(json.dumps({'jobs':jobs,'protocol_sha256':hashlib.sha256(proto.read_bytes()).hexdigest(),'binary_sha256':hashlib.sha256(pathlib.Path(exe).read_bytes()).hexdigest(),'runner_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'fit_performed':False},indent=2))
 def run(j):
  mode,size,pages,pat,qd=j;key=f'{mode}-{size}-{pages}-{pat}';a=trace(size,pages,pat);raw=''.join(f'{x}\n' for x in a);t=time.monotonic();status={'valid':False}
  with gzip.open(out/(key+'.input.gz'),'wt') as f:f.write(raw)
  try:
   r=subprocess.run([exe,str(size),str(qd),str(pages),mode],input=raw,text=True,capture_output=True,timeout=1800);status['exit']=r.returncode
   with gzip.open(out/(key+'.jsonl.gz'),'wt') as f:f.write(r.stdout)
   (out/(key+'.stderr')).write_text(r.stderr);assert r.returncode==0,r.stderr
   result=check(r.stdout,a,size,qd,pages);status['valid']=True
  except subprocess.TimeoutExpired as e:
   with gzip.open(out/(key+'.partial.gz'),'wb') as f:f.write(e.stdout or b'')
   (out/(key+'.stderr')).write_bytes(e.stderr or b'');status['error']='timeout';raise
  finally:status['wall_seconds']=time.monotonic()-t;(out/(key+'.status.json')).write_text(json.dumps(status))
  result.update(mode=mode,size=size,pages=pages,pattern=pat,qd=qd);print(key,result['window_GBps'],result['steady'],flush=True);return result
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(run,jobs))
 lengths=[]
 for size in [256,4096]:
  pair=[r for r in results if r['mode']=='payload-v3' and r['size']==size and r['pattern']=='sequential'];rate=[r['window_GBps'][-1] for r in pair];lengths.append({'size':size,'within_5_percent':max(rate)/min(rate)<=1.05})
 (out/'summary.json').write_text(json.dumps({'runs':results,'length_checks':lengths,'hardware_calibrated':False,'paper_curve_reproduced':False,'performance_ready':False},indent=2))
if __name__=='__main__':main()
