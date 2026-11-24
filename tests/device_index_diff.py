"""Separate original-scanning binary is the oracle; no stage-index implementation imported."""
import pathlib,subprocess,json,random,sys,hashlib
before,after=map(lambda s:str(pathlib.Path(s).resolve()),sys.argv[1:3]);out=pathlib.Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
sequential=list(range(1024));permutation=sequential.copy();random.Random(8301).shuffle(permutation)
cases=[('cold-wide',256,1024,0,0,4096,permutation),('hot-wide',256,1024,1,0,4096,permutation),('chain',256,1024,0,1,4096,permutation),('small-window',4096,16,0,0,256,sequential)]
def compare(expected, actual):
 assert expected==actual, "request/time/event differential mismatch"

results=[]
for name,size,qd,hot,dep,mocs,pages in cases:
 raw=''.join(str(p)+'\n' for p in pages);observations=[]
 for kind,exe in [('scan',before),('index',after)]:
  r=subprocess.run([exe,str(size),str(qd),str(hot),str(dep),str(mocs)],input=raw,text=True,capture_output=True,timeout=180)
  (out/f'{name}-{kind}.jsonl').write_text(r.stdout);(out/f'{name}-{kind}.stderr').write_text(r.stderr)
  assert r.returncode==0,(name,kind,r.stderr)
  rows=[json.loads(x) for x in r.stdout.splitlines()];assert len(rows)==1025
  requests=rows[:-1];summary=rows[-1]
  assert {x['id'] for x in requests}==set(range(10000,11024)) and summary['requests']==1024
  assert max(x['complete_ps'] for x in requests)==summary['elapsed_ps']
  assert all(x['complete_ps']>=x['submit_ps'] for x in requests)
  assert summary['peak']==(1 if dep else qd)
  observations.append((r.stdout,r.stderr))
 compare(observations[0],observations[1])
 # Negative evidence: changing any completion, losing a request, or corrupting
 # the ordered event fingerprint must invalidate the comparison.
 good=observations[0];bad=[(good[0].replace('"complete_ps":','"corrupted_complete_ps":',1),good[1]),('\n'.join(good[0].splitlines()[1:]),good[1]),(good[0],good[1]+'corrupted digest\n')]
 for x in bad:
  try:compare(good,x)
  except AssertionError:pass
  else:raise AssertionError("accepted corrupted differential evidence")
 results.append({'case':name,'byte_identical_requests_and_event_digest':True,'sha256':hashlib.sha256(good[0].encode()).hexdigest()})
(out/'verdict.json').write_text(json.dumps({'cases':results,'corrupt_records_rejected':12,'scope':'scan implementation versus stage index, with independent completion/count/peak invariants','performance_ready':False},indent=2));print(results)
