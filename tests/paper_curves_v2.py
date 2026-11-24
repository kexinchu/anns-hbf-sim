"""Frozen v2 finite-batch diagnostics, with independent per-record validation."""
import argparse, concurrent.futures, csv, hashlib, itertools, json, math, pathlib, random, shutil, subprocess, time
ROOT=pathlib.Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def cases(cfg):
 return [dict(size=s,cache=c,pattern=p,qd=q,mocs=m,seed=z) for s,c,p,q,m,z in itertools.product(cfg['parent_bytes'],['cold','hot'],cfg['patterns'],cfg['qd_grid'],[cfg['mocs_primary_per_channel'],cfg['mocs_control_per_channel']],cfg['validation_seeds'])]
def addresses(c):
 a=list(range(1024))
 if c['pattern']!='sequential': random.Random(c['seed']).shuffle(a)
 return [i*(c['size'] if c['pattern']=='sequential' else 4096) for i in a]
def validate(c,addr,stdout,stderr):
 data=[json.loads(x) for x in stdout.splitlines()];assert len(data)==1025
 req,s=data[:-1],data[-1];n=1024;window=1 if c['pattern']=='pointer_chasing' else c['qd']
 assert {x['id'] for x in req}==set(range(10000,11024))
 by_id={x['id']-10000:x for x in req}
 assert all(x['kind']=='request' and x['complete_ps']>=x['submit_ps']>=0 for x in req)
 assert [x['complete_ps'] for x in req]==sorted(x['complete_ps'] for x in req)
 assert all(by_id[i]['submit_ps']==0 for i in range(window))
 assert all(by_id[i]['submit_ps']==req[i-window]['complete_ps'] for i in range(window,n)), 'arrival protocol mismatch'
 assert s['requests']==n and s['peak']==window and s['bytes']==c['size'] and s['qd']==c['qd']
 assert s['hot']==int(c['cache']=='hot') and s['dependent']==int(c['pattern']=='pointer_chasing')
 expected=0 if c['cache']=='hot' else len({a//4096 for a in addr})
 assert s['senses']==expected and s['useful_bytes']==n*c['size'] and s['elapsed_ps']==req[-1]['complete_ps']
 assert 'remaining=0' in stderr and 'trace_count=' in stderr and f'mocs={c["mocs"]}' in stderr
 # Independent service accounting: every successful 64B command returns 80 service bytes.
 counts=[0]*16
 for a in addr:
  for off in range(0,c['size'],64):counts[((a+off)//4096)%16]+=1
 service_ps=(80*1000+93)//94
 assert s['elapsed_ps']>=max(counts)*service_ps, 'violated per-channel service budget'
 if expected:assert s['elapsed_ps']>=2720000
 if expected and window==1:assert s['elapsed_ps']>=expected*2720000
 lat=sorted(x['complete_ps']-x['submit_ps'] for x in req)
 return dict(**c,elapsed_ps=s['elapsed_ps'],GBps=s['useful_bytes']*1000/s['elapsed_ps'],p99_ps=lat[math.ceil(.99*n)-1],senses=expected,unique_pages=len({a//4096 for a in addr}),page_efficiency=s['useful_bytes']/(4096*expected) if expected else '',paper_GBps='',relative_error_to_paper='unavailable')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('out');ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
 protocol=ROOT/'calibration/paper-curves/protocol-v2.json';cfg=json.loads(protocol.read_text())
 assert sha(protocol)==protocol.with_suffix('.sha256').read_text().split()[0]
 out=pathlib.Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
 shutil.copyfile(a.exe,out/'probe.bin');(out/'probe.bin').chmod(0o755);exe=str(out/'probe.bin')
 grid=cases(cfg)
 manifest={'protocol_sha256':sha(protocol),'binary_sha256':sha(exe),'runner_sha256':sha(__file__),'cases':grid,'fit':{'performed':False,'observations_used':[]},'validation_seeds':cfg['validation_seeds'],'workers':a.workers,'timeout_seconds_per_case':900,'performance_ready':False,'hardware_calibrated':False}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
 def run(c):
  key='-'.join(str(c[k]) for k in ['size','cache','pattern','qd','mocs','seed']);addr=addresses(c);raw=''.join(f'{x}\n' for x in addr);(out/(key+'.input')).write_text(raw)
  t=time.monotonic();status={'case':c,'valid':False}
  try:
   r=subprocess.run([exe,str(c['size']),str(c['qd']),str(int(c['cache']=='hot')),str(int(c['pattern']=='pointer_chasing')),str(c['mocs']),'byte-addresses'],input=raw,text=True,capture_output=True,timeout=900)
   (out/(key+'.jsonl')).write_text(r.stdout);(out/(key+'.stderr')).write_text(r.stderr);status['exit']=r.returncode
   assert r.returncode==0,r.stderr
   result=validate(c,addr,r.stdout,r.stderr);status['valid']=True
  except subprocess.TimeoutExpired as e:
   (out/(key+'.partial')).write_bytes(e.stdout or b'');(out/(key+'.stderr')).write_bytes(e.stderr or b'');status['error']='timeout';raise
  except Exception as e:status['error']=str(e);raise
  finally:
   status['wall_seconds']=time.monotonic()-t;(out/(key+'.status.json')).write_text(json.dumps(status,indent=2))
  print(key,round(result['GBps'],6),flush=True);return result
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:rows=list(pool.map(run,grid))
 for size,cache,mocs,seed in itertools.product(cfg['parent_bytes'],['cold','hot'],[4096,256],cfg['validation_seeds']):
  r=[x for x in rows if (x['size'],x['cache'],x['mocs'],x['seed'],x['pattern'])==(size,cache,mocs,seed,'pointer_chasing')]
  assert len({(x['elapsed_ps'],x['p99_ps'],x['senses']) for x in r})==1,'ineffective chain QD changed result'
 with (out/'curves.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 (out/'verdict.json').write_text(json.dumps({'cases':len(rows),'checks':'PASS','paper_curve_reproduced':False,'hardware_calibrated':False,'performance_ready':False},indent=2))
if __name__=='__main__':main()
