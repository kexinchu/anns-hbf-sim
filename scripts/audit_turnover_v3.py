"""Read-only revalidation and summary from retained raw traces, including failed runs."""
import gzip,json,pathlib,sys,hashlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tests'))
from turnover_v3 import check,trace
root=pathlib.Path(sys.argv[1]);results=[];invalid=[]
for folder in ['results','retry-input-limit']:
 for p in sorted((root/folder).glob('*.status.json')):
  key=p.name.removesuffix('.status.json');status=json.loads(p.read_text())
  if status['exit']!=0:
   invalid.append({'artifact':str(p.relative_to(root)),'status':status});continue
  mode,version,size,pages,pattern=key.split('-');mode+='-'+version;size=int(size);pages=int(pages);qd=1 if pattern=='dependent' else 128
  addrs=list(map(int,gzip.open(p.parent/(key+'.input.gz'),'rt').read().split()))
  assert addrs==trace(size,pages,pattern),'input differs from frozen generator'
  data=gzip.open(p.parent/(key+'.jsonl.gz'),'rt').read();r=check(data,addrs,size,qd,pages)
  r.update(mode=mode,size=size,pages=pages,pattern=pattern,qd=qd,artifact=str(p.relative_to(root)));results.append(r)
assert len(results)==12 and len(invalid)==2
lengths=[]
for size in [256,4096]:
 pair=sorted([r for r in results if r['mode']=='payload-v3' and r['size']==size and r['pattern']=='sequential'],key=lambda r:r['pages'])
 assert [r['pages'] for r in pair]==[3072,6144]
 rates=[r['window_GBps'][-1] for r in pair];lengths.append({'size':size,'rates_GBps':rates,'within_5_percent':max(rates)/min(rates)<=1.05})
summary={'runs':results,'invalid_retained':invalid,'length_checks':lengths,'fit_performed':False,'hardware_calibrated':False,'paper_curve_reproduced':False,'performance_ready':False}
(root/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps({'valid':len(results),'steady':sum(r['steady'] for r in results),'length_checks':lengths},indent=2))
(root/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root)}\n' for p in sorted(root.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
