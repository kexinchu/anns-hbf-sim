"""Re-run fixed cold 4-KiB window sensitivity; never treat a timeout as a result.
Usage: python3 run-diagnostic.py /absolute/path/to/probe fresh-output-directory [qd=1024]
The probe source is credit_probe.cpp; link against the current ON EventLab library.
"""
import hashlib,json,pathlib,subprocess,sys,time
exe=pathlib.Path(sys.argv[1]).resolve();out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=False)
qd=int(sys.argv[3]) if len(sys.argv)>3 else 1024
assert qd in [128,1024]
pages=''.join(str(i)+'\n' for i in range(1024));records=[]
for m in [256,4096]:
 start=time.monotonic();cmd=[str(exe),'4096',str(qd),'0','0',str(m)]
 with (out/f'mocs-{m}.jsonl').open('w') as stdout,(out/f'mocs-{m}.stderr').open('w') as stderr:
  try:
   r=subprocess.run(cmd,input=pages,text=True,stdout=stdout,stderr=stderr,timeout=300)
   status={'mocs':m,'exit':r.returncode}
  except subprocess.TimeoutExpired:status={'mocs':m,'timeout_seconds':300}
 status.update(wall_seconds=time.monotonic()-start,command=cmd)
 records.append(status);(out/'status.json').write_text(json.dumps(records,indent=2))
(out/'binary-sha256.txt').write_text(hashlib.sha256(exe.read_bytes()).hexdigest()+'\n')
if any(x.get('exit')!=0 for x in records):raise SystemExit('Incomplete diagnostic: no throughput verdict')
