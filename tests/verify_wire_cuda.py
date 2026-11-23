"""Actual EventLab plus CUDA functional test, independent native IVF answer oracle."""
import json,pathlib,subprocess,sys,uuid
out=pathlib.Path(sys.argv[2])/uuid.uuid4().hex;out.mkdir(parents=True)
db=[[i//64*100+(i*17+j*13)%23-11 for j in range(32)] for i in range(256)]
for mode in ['','wire_writeback','wrong_address','corrupt_payload','early_consume']:
 p=subprocess.run([sys.argv[1],'100000','10000','2','10000',mode],text=True,capture_output=True,timeout=90)
 (out/(mode or 'clean')).write_text(json.dumps(dict(stdout=p.stdout,stderr=p.stderr,exit=p.returncode),indent=2))
 if mode in ['wrong_address','corrupt_payload','early_consume']:
  assert p.returncode!=0,(mode,'mutation escaped');continue
 assert p.returncode==0,p.stderr
 rows=[json.loads(x) for x in p.stdout.splitlines()]
 if len(sys.argv)>3 and sys.argv[3]=='CUDA':assert rows[0].get('backend')=='CUDA_A6000'
 answers=[x for x in rows if 'result_q' in x];assert len(answers)==2
 for x in answers:
  q=db[[27,172][x['result_q']]]
  lists=sorted(range(4),key=lambda l:(sum((l*100-y)**2 for y in q),l))[:2]
  ids=[i for l in lists for i in range(l*64,(l+1)*64)]
  expected=sorted(ids,key=lambda i:(sum((a-b)**2 for a,b in zip(db[i],q)),i))[:10]
  assert x['ids']==expected
 if mode=='wire_writeback':assert [x['wire_writebacks'] for x in rows if 'wire_writebacks' in x]==[8]
 assert rows[-1]['status']=='PASS'
print('PASS EventLab + page owner: native IVF equivalence, eight sequential writebacks, three negative cases; performance disabled')
