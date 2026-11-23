"""Independent externally observable reset/transport reference, no native imports."""
import json,pathlib,subprocess,sys
exe=str(pathlib.Path(sys.argv[1]).resolve());out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
# Global 128 -> channel 0 local 64 under 64-byte two-channel striping.
v=(((7*0x9e3779b97f4a7c15)&((1<<64)-1))^2)%97+20
scores=[sum((v+(k*32+j)%17-3)**2 for j in range(32)) for k in range(32)]
def run(t,o,m='',mode='read'):
 args=[exe,str(t),str(o),m,mode]
 r=subprocess.run(args,capture_output=True,text=True,timeout=45)
 p=out/f'{mode}-{t}-{o}{"-"+m if m else ""}'
 p.with_suffix('.stdout').write_text(r.stdout);p.with_suffix('.stderr').write_text(r.stderr)
 p.with_suffix('.run.json').write_text(json.dumps({'args':args,'exit':r.returncode}))
 return r

def check(r,t,mode="read"):
 assert r.returncode==0,r.stderr
 a,b,c=map(json.loads,r.stdout.splitlines())
 assert a=={'type':t,'domains':[1,1,int(t>=1),int(t==2)],'en':int(t!=2),'ready':0},'reset domains'
 assert b['recovered'] and b['other_banks']>0 and b['old_external_packets']==1,'quiescence escape'
 assert c['old_success']==(t==0) and c['old_calls']==1 and c['other_calls']==1,'retention policy'
 assert c['new_calls']==2,'callback alias'
 assert c['stale_accepted'] is False,'stale accepted'
 assert c['stale_request_accepted'] is False,'stale request accepted'
 assert c['drained'] and c['external_pending']==0,'resource leak'
 expected=scores if mode=='read' else [sum((102%97+20+(k*32+j)%17-3)**2 for j in range(32)) for k in range(32)]
 assert c['scores']==expected,'distance mismatch'
for mode in ['read','write']:
 for t in range(3):
  for o in range(3):check(run(t,o,mode=mode),t,mode)
for m,reason in [('accept_old_request','stale request accepted'),('accept_stale','stale accepted'),('alias_callback','callback alias'),('bad_score','distance mismatch')]:
 r=run(2,0,m)
 try:check(r,2)
 except AssertionError as e:assert str(e)==reason,(m,str(e))
 else:raise AssertionError(f'{m} escaped')
r=run(3,0);assert r.returncode!=0 and 'reserved reset type' in r.stderr
print('PASS: 18 read/write reset-type/order schedules; 4 independently rejected mutations; reserved type rejected')
